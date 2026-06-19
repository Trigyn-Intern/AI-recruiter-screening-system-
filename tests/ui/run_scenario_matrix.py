"""Automation runner for the data-driven Playwright suite.

This is what the manager asked for: one entry point that

  1. Verifies the requested Ollama model is installed locally (and pulls it
     if it is missing).
  2. Starts the Streamlit app on a free port if it is not already running
     (or kills a stale one and re-starts it, so the test always sees a
     fresh app).
  3. Runs the parameterized Playwright scenario matrix.
  4. Stops the Streamlit app it started when the run finishes.

Usage examples::

    # Run every scenario defined in scenarios.yaml
    python tests/ui/run_scenario_matrix.py

    # Run only scenarios that mention "python" in their id
    python tests/ui/run_scenario_matrix.py --filter python

    # Override the scenario config location
    python tests/ui/run_scenario_matrix.py --config tests/data/scenarios.yaml

    # Dry run: list what would be executed, do nothing
    python tests/ui/run_scenario_matrix.py --dry-run

    # Do NOT stop Streamlit when the test finishes (handy for poking at it)
    python tests/ui/run_scenario_matrix.py --keep-streamlit

Notes:
  - The runner ALWAYS starts its own Streamlit on the chosen port. If
    something else (another process, a stale Streamlit) is already bound
    to that port, the runner kills it and starts fresh. This makes the
    result deterministic and avoids the "passes only when the app is
    already up" failure mode.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "tests" / "data" / "scenarios.yaml"
STREAMLIT_LOG = ROOT / "streamlit.log"


def _log(message: str) -> None:
    print(f"[run_scenario_matrix] {message}", flush=True)


# ---- CLI ----------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to the scenario YAML config (default: tests/data/scenarios.yaml).",
    )
    parser.add_argument(
        "--filter",
        default=os.environ.get("SCENARIO_FILTER", ""),
        help="Only run scenarios whose id contains this substring.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("STREAMLIT_PORT", "8501")),
        help="Streamlit port (default: 8501).",
    )
    parser.add_argument(
        "--keep-streamlit",
        action="store_true",
        help="Do not stop Streamlit after the run.",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse a Streamlit already bound to --port instead of starting "
             "a fresh one. Default behaviour is to always start fresh.",
    )
    parser.add_argument(
        "--pytest-args",
        default="",
        help="Extra args forwarded to pytest, e.g. '-k frontend'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print scenarios that would be run and exit without executing them.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Scenario config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def filter_scenarios(config: dict, needle: str) -> list[dict]:
    scenarios = config.get("scenarios") or []
    if needle:
        scenarios = [s for s in scenarios if needle in s.get("id", "")]
    if not scenarios:
        raise SystemExit(f"No scenarios left after applying filter {needle!r}.")
    return scenarios


# ---- Ollama helpers ------------------------------------------------------

def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def get_installed_models() -> list[str]:
    if not ollama_installed():
        return []
    try:
        result = subprocess.run(
            ["ollama", "list"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

    names: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("NAME"):
            continue
        first = line.split()[0]
        if ":" not in first:
            first = f"{first}:latest"
        names.append(first)
    return names


def ensure_models(models: list[str]) -> None:
    if not ollama_installed():
        raise SystemExit(
            "Ollama CLI not found on PATH. Install from https://ollama.com."
        )

    installed = set(get_installed_models())
    for model in models:
        bare = model.split(":", 1)[0]
        already = model in installed or f"{bare}:latest" in installed
        if already:
            _log(f"Ollama model '{model}' is already installed.")
            continue
        _log(f"Ollama model '{model}' not found locally. Pulling...")
        subprocess.run(["ollama", "pull", bare], check=True)


# ---- Streamlit lifecycle -------------------------------------------------

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.connect(("127.0.0.1", port))
        except OSError:
            return False
        return True


def pid_listening_on(port: int) -> list[int]:
    """Return the PIDs that own the given TCP port (Windows-friendly)."""

    pids: set[int] = set()
    try:
        output = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return []

    needle = f":{port}"
    for line in output.splitlines():
        if "LISTENING" not in line:
            continue
        if needle not in line:
            continue
        parts = line.split()
        if parts:
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                continue
    return sorted(pids)


def kill_listeners(port: int) -> None:
    """Kill any process listening on the given port."""

    pids = pid_listening_on(port)
    if not pids:
        return
    _log(f"Killing {len(pids)} process(es) bound to port {port}: {pids}")
    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                check=False,
                capture_output=True,
            )
        except FileNotFoundError:
            # Fallback for non-Windows: use a SIGTERM.
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    # Give the OS a moment to release the port.
    for _ in range(20):
        if not port_in_use(port):
            return
        time.sleep(0.5)


def wait_for_http(url: str, timeout: float = 60.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(1.0)
    return False


def start_streamlit(port: int) -> subprocess.Popen:
    """Always start a fresh Streamlit bound to `port`.

    If a stale process is already on the port we kill it first so we
    don't get the classic "test passes only when Streamlit was already up"
    failure mode. The Popen handle of the new process is returned.
    """

    if port_in_use(port):
        _log(
            f"Port {port} is already in use. Killing the existing process "
            "so we always start fresh."
        )
        kill_listeners(port)

    STREAMLIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_handle = STREAMLIT_LOG.open("ab", buffering=0)

    _log(f"Starting Streamlit on port {port}. Logs -> {STREAMLIT_LOG}")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

    url = f"http://localhost:{port}"
    if not wait_for_http(url, timeout=90):
        process.terminate()
        raise SystemExit(
            f"Streamlit did not become ready at {url} within 90 seconds. "
            f"See {STREAMLIT_LOG} for details."
        )

    _log(f"Streamlit is up at {url}.")
    return process


def stop_streamlit(process: Optional[subprocess.Popen]) -> None:
    if process is None:
        return
    _log("Stopping Streamlit...")
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


# ---- Pytest invocation ---------------------------------------------------

def run_pytest(
    config_path: Path,
    base_url: str,
    scenarios: list[dict],
    extra_args: str,
) -> int:
    env = os.environ.copy()
    env["APP_BASE_URL"] = base_url
    env["SCENARIO_CONFIG"] = str(config_path)

    pytest_args = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ui/test_scenario_matrix.py",
        "-v",
        "--tb=short",
    ]

    if extra_args:
        pytest_args.extend(extra_args.split())

    summary = {
        "base_url": base_url,
        "config": str(config_path),
        "scenarios": [s["id"] for s in scenarios],
    }
    _log("Running pytest with scenarios: " + json.dumps(summary, indent=2))

    return subprocess.call(pytest_args, cwd=str(ROOT), env=env)


# ---- Entry point ---------------------------------------------------------

def main() -> int:
    args = parse_args()

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    scenarios = filter_scenarios(config, args.filter)

    if args.dry_run:
        _log("=== DRY RUN ===")
        _log(f"Config file: {config_path}")
        _log(f"Found {len(scenarios)} matching scenarios:")
        for idx, s in enumerate(scenarios, start=1):
            _log(f"  {idx}. ID: {s['id']}")
            _log(f"     Model: {s['model']}")
            _log(f"     JD File: {s['jd_file']}")
            _log(f"     Resumes: {s['resume_files']}")
            if "expected_resume" in s:
                _log(f"     Expected Top Resume: {s['expected_resume']}")
            if "expected_min_score" in s:
                _log(f"     Expected Min Score: {s['expected_min_score']}")
        _log("=== END DRY RUN ===")
        return 0

    base_port = args.port

    # Reuse-existing keeps the user's manual Streamlit alive but is OFF by
    # default so the runner is reproducible.
    streamlit_proc: Optional[subprocess.Popen] = None
    if args.reuse_existing and port_in_use(base_port):
        _log(
            f"Reusing existing listener on port {base_port} (--reuse-existing)."
        )
    else:
        models = sorted({s["model"] for s in scenarios})
        _log(f"Ensuring Ollama models are available: {models}")
        ensure_models(models)

        streamlit_proc = start_streamlit(base_port)

    base_url = f"http://localhost:{base_port}"

    try:
        return run_pytest(config_path, base_url, scenarios, args.pytest_args)
    finally:
        if not args.keep_streamlit and streamlit_proc is not None:
            stop_streamlit(streamlit_proc)


if __name__ == "__main__":
    sys.exit(main())