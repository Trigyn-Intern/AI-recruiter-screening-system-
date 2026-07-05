"""Automation runner for the Playwright scenario matrix.

Responsibilities:

* Verify the local Ollama install is running and pull any missing models
  that the scenario config references.
* Boot the FastAPI analyzer (``uvicorn api:api``) and the React dev
  server (``vite``) if they are not already listening on the expected
  ports.
* Optionally launch the Node auth API (Express + Mongo) so the React
  login screen has a backend.
* Wait for each service to respond on its health endpoint.
* Invoke pytest against ``tests/ui/test_scenario_matrix.py``, passing
  ``--scenario-config`` / ``--scenario-filter`` through.
* Tear the spawned processes down unless ``--keep-streamlit`` (kept for
  backwards compat - alias for "keep all servers") was passed.
* Support ``--dry-run`` to print the scenario matrix and the commands it
  would run without actually invoking Ollama, uvicorn, or pytest.

CLI:

    python tests/ui/run_scenario_matrix.py
    python tests/ui/run_scenario_matrix.py --filter python_ml_llama32
    python tests/ui/run_scenario_matrix.py --dry-run
    python tests/ui/run_scenario_matrix.py --config tests/data/scenarios.yaml
"""

from __future__ import annotations

import argparse
import contextlib
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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DEFAULT_CONFIG = HERE.parent / "data" / "scenarios.yaml"

DEFAULT_API_PORT = int(os.environ.get("API_PORT", "8000"))
DEFAULT_WEB_PORT = int(os.environ.get("WEB_PORT", "5173"))
DEFAULT_AUTH_PORT = int(os.environ.get("AUTH_PORT", "4000"))

# FastAPI app object is named ``api`` inside api.py; load it via the
# ``api:api`` import path so uvicorn doesn't need an ``app`` symbol.
UVICORN_APP = os.environ.get("UVICORN_APP", "api:api")

def _normalize_ollama_host(value):
    """Accept bare `127.0.0.1:11434`, `localhost`, or full URLs.
    Always return a value `urllib.request.urlopen` can use."""
    v = (value or "").strip()
    if not v:
        return "http://127.0.0.1:11434"
    if "://" in v:
        return v.rstrip("/")
    if v.startswith("127.") or v.startswith("localhost") or (":" in v and not v.startswith("/")):
        return "http://" + v
    return v

OLLAMA_HOST = _normalize_ollama_host(os.environ.get("OLLAMA_HOST"))


# ------------------------------------------------------------
# YAML + filter
# ------------------------------------------------------------

def load_scenarios(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise SystemExit(f"{path} must define a non-empty 'scenarios' list.")
    return scenarios


def filter_scenarios(
    scenarios: List[Dict[str, Any]], raw_filter: Optional[str]
) -> List[Dict[str, Any]]:
    if not raw_filter:
        return list(scenarios)

    wanted = {token.strip() for token in raw_filter.replace(",", " ").split() if token.strip()}
    selected = [s for s in scenarios if s.get("id") in wanted]
    missing = wanted - {s.get("id") for s in selected}
    if missing:
        raise SystemExit(f"Unknown scenario ids: {sorted(missing)}")
    return selected


# ------------------------------------------------------------
# Ollama
# ------------------------------------------------------------

def _ollama_list() -> List[str]:
    """Return the names of models currently installed locally."""
    request = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        raise SystemExit(
            f"Ollama is not reachable at {OLLAMA_HOST}. Start it with `ollama serve`."
        )
    return [model.get("name", "") for model in payload.get("models", [])]


def ensure_ollama_models(required: Iterable[str]) -> None:
    required_list = list(required)
    if not required_list:
        return

    try:
        installed = {name.split(":")[0] for name in _ollama_list()}
    except SystemExit as e:
        raise e

    required_set = {name.split(":")[0] for name in required_list}
    missing = sorted(required_set - installed)
    if not missing:
        print(f"[ollama] all required models already present: {sorted(required_set)}")
        return

    print(f"[ollama] pulling missing models: {missing}")
    for model in missing:
        try:
            subprocess.run(["ollama", "pull", model], check=True, cwd=REPO_ROOT)
        except FileNotFoundError:
            raise SystemExit(
                f"Error: 'ollama' executable not found in PATH. Please install Ollama or ensure it is in your PATH to pull {model}."
            )


# ------------------------------------------------------------
# port helpers
# ------------------------------------------------------------

def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_http(url: str, timeout_seconds: int = 60, label: str = "") -> None:
    print(f"[runner] waiting for {label or url} to respond...", end="", flush=True)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    print(" OK")
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            print(".", end="", flush=True)
            time.sleep(0.5)
    print(" FAILED")
    raise SystemExit(f"Timed out waiting for {label or url} to respond.")


# ------------------------------------------------------------
# service starters
# ------------------------------------------------------------

def _spawn(command: Sequence[str], cwd: Path, log_path: Path) -> subprocess.Popen:
    log_handle = log_path.open("ab")
    print(f"[runner] {' '.join(command)}  (logs -> {log_path})")
    return subprocess.Popen(
        list(command),
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        # New process group so we can terminate children cleanly.
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        preexec_fn=os.setsid if os.name != "nt" else None,
    )


def start_api(
    api_port: int,
    log_path: Path,
    venv_python: Path,
) -> subprocess.Popen:
    """Start the FastAPI analyzer (uvicorn api:api)."""
    if port_in_use(api_port):
        print(f"[runner] FastAPI already listening on :{api_port}; reusing it.")
        return _noop_process()

    print("[runner] starting FastAPI analyzer")
    return _spawn(
        [
            str(venv_python),
            "-m",
            "uvicorn",
            UVICORN_APP,
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=REPO_ROOT,
        log_path=log_path,
    )


def start_web(
    web_port: int,
    log_path: Path,
) -> subprocess.Popen:
    """Start the React dev server (npm run dev)."""
    if port_in_use(web_port):
        print(f"[runner] Vite already listening on :{web_port}; reusing it.")
        return _noop_process()

    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("`npm` is not on PATH. Install Node.js to run the React UI.")

    print("[runner] starting React dev server (vite)")
    return _spawn(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(web_port)],
        cwd=REPO_ROOT / "frontend",
        log_path=log_path,
    )


def start_auth(
    auth_port: int,
    log_path: Path,
) -> subprocess.Popen:
    """Start the Node auth API (Express + Mongo)."""
    if port_in_use(auth_port):
        print(f"[runner] Auth API already listening on :{auth_port}; reusing it.")
        return _noop_process()

    node = shutil.which("node")
    if not node:
        raise SystemExit("`node` is not on PATH. Install Node.js to run the auth API.")

    print("[runner] starting Node auth API")
    return _spawn(
        [node, "backend/server.js"],
        cwd=REPO_ROOT,
        log_path=log_path,
    )


def _noop_process() -> subprocess.Popen:
    """A placeholder Popen for ports that were already in use."""
    return subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])


# ------------------------------------------------------------
# process lifecycle
# ------------------------------------------------------------

class ServiceSupervisor:
    """Spawns services, waits for their health, and tears them down on exit."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.processes: List[Tuple[str, subprocess.Popen]] = []

    def add(self, label: str, process: subprocess.Popen) -> None:
        self.processes.append((label, process))

    def terminate(self) -> None:
        for label, process in self.processes:
            if process.poll() is not None:
                continue
            print(f"[runner] stopping {label}")
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=10)
            except (ProcessLookupError, OSError):
                pass


@contextlib.contextmanager
def supervised_services(log_dir: Path):
    supervisor = ServiceSupervisor(log_dir)
    try:
        yield supervisor
    finally:
        supervisor.terminate()


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Path to scenarios.yaml (default: tests/data/scenarios.yaml)")
    parser.add_argument("--filter", dest="scenario_filter", type=str, default="",
                        help="Comma- or whitespace-separated list of scenario IDs to run.")
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    parser.add_argument("--web-port", type=int, default=DEFAULT_WEB_PORT)
    parser.add_argument("--auth-port", type=int, default=DEFAULT_AUTH_PORT)
    parser.add_argument("--no-auth", action="store_true",
                        help="Skip starting the Node auth API (assumes one is already running).")
    parser.add_argument("--keep-streamlit", action="store_true",
                        help="Keep spawned services alive after pytest finishes.")
    parser.add_argument("--pytest-args", type=str, default="",
                        help="Extra arguments forwarded to pytest.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the scenario matrix and the commands that would run, "
                             "without starting services or invoking pytest.")
    parser.add_argument("--log-dir", type=Path, default=HERE / "logs",
                        help="Directory for service + pytest logs.")
    parser.add_argument("--report-dir", dest="report_dir", type=Path, default=None,
                        help="If set, write a structured HTML report here. The JUnit "
                             "JSON is written alongside it. The renderer is "
                             "tests/render_report.py.")
    parser.add_argument("--junit", dest="junit_path", type=Path, default=None,
                        help="Path to write the raw JUnit JSON. Defaults to "
                             "<report-dir>/junit-<timestamp>.json when --report-dir "
                             "is set. Ignored otherwise.")
    parser.add_argument("--open-report", dest="open_report", action="store_true",
                        help="Open the rendered HTML report in the default browser.")
    return parser.parse_args(argv)


def _venv_python() -> Path:
    candidates: List[Path] = []
    if os.name == "nt":
        candidates.append(REPO_ROOT / "venv" / "Scripts" / "python.exe")
    else:
        candidates.append(REPO_ROOT / "venv" / "bin" / "python")
        candidates.append(REPO_ROOT / "venv" / "Scripts" / "python.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _print_dry_run(scenarios: List[Dict[str, Any]]) -> None:
    print("[dry-run] scenario matrix:")
    for scenario in scenarios:
        print(f"  - {scenario['id']}: model={scenario['model']} jd={scenario['jd_file']}")
    print("[dry-run] pytest --scenario-config=...  tests/ui/test_scenario_matrix.py")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    scenarios = filter_scenarios(load_scenarios(args.config), args.scenario_filter)
    required_models = sorted({scenario["model"] for scenario in scenarios})
    venv_python = _venv_python()

    env_overrides = {
        "API_BASE_URL": f"http://127.0.0.1:{args.api_port}",
        "WEB_BASE_URL": f"http://localhost:{args.web_port}",
        "AUTH_API_URL": f"http://localhost:{args.auth_port}",
    }
    for key, value in env_overrides.items():
        os.environ[key] = value

    if args.dry_run:
        _print_dry_run(scenarios)
        print(f"[dry-run] ollama models that would be checked: {required_models}")
        return 0

    ensure_ollama_models(required_models)

    with supervised_services(args.log_dir) as supervisor:
        api_process = start_api(args.api_port, args.log_dir / "api.log", venv_python)
        supervisor.add("fastapi", api_process)
        _wait_for_http(f"http://127.0.0.1:{args.api_port}/health", label="FastAPI /health")

        web_process = start_web(args.web_port, args.log_dir / "web.log")
        supervisor.add("vite", web_process)
        _wait_for_http(f"http://localhost:{args.web_port}/", label="React dev server")

        if not args.no_auth:
            auth_process = start_auth(args.auth_port, args.log_dir / "auth.log")
            supervisor.add("auth", auth_process)
            _wait_for_http(
                f"http://localhost:{args.auth_port}/api/health", label="Auth API"
            )

        pytest_cmd = [
            str(venv_python),
            "-m",
            "pytest",
            str(HERE / "test_scenario_matrix.py"),
            f"--scenario-config={args.config}",
        ]
        if args.scenario_filter:
            pytest_cmd.append(f"--scenario-filter={args.scenario_filter}")
        pytest_cmd.append("-v")
        if args.pytest_args:
            pytest_cmd.extend(args.pytest_args.split())

        # Forward the URL overrides to pytest so the test sees the same
        # ports the runner bound.
        pytest_env = os.environ.copy()
        pytest_env["API_BASE_URL"] = env_overrides["API_BASE_URL"]
        pytest_env["WEB_BASE_URL"] = env_overrides["WEB_BASE_URL"]
        pytest_env["AUTH_API_URL"] = env_overrides["AUTH_API_URL"]

        # Resolve JUnit + HTML output paths. --report-dir drives both.
        if args.report_dir is not None:
            args.report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            junit_path = args.report_dir / ("junit-" + timestamp + ".json")
            html_path  = args.report_dir / ("scenario-report-" + timestamp + ".html")
        elif args.junit_path is not None:
            junit_path = args.junit_path
            html_path  = None
        else:
            junit_path = None
            html_path  = None

        if junit_path is not None:
            junit_path.parent.mkdir(parents=True, exist_ok=True)
            pytest_cmd.append("--junit-xml=" + str(junit_path))
            print("[runner] JUnit will be written to: " + str(junit_path))

        print("[runner] " + " ".join(pytest_cmd))
        result = subprocess.run(pytest_cmd, env=pytest_env)

        if args.keep_streamlit:
            print("[runner] --keep-streamlit set; leaving services running.")

    # Render the HTML report outside the services context.
    if html_path is not None and junit_path is not None and junit_path.exists():
        renderer = REPO_ROOT / "tests" / "render_report.py"

        if not renderer.exists():
            print("[runner] WARNING: renderer not found at " + str(renderer) + "; skipping HTML report.")
        else:
            stamp = junit_path.stem.replace("junit-", "", 1)
            filter_value = args.scenario_filter or "(all)"
            render_cmd = [
                sys.executable,
                str(renderer),
                "--junit",  str(junit_path),
                "--output", str(html_path),
                "--filter", filter_value,
                "--stamp",  stamp,
            ]
            print("[runner] rendering report: " + " ".join(render_cmd))
            render_result = subprocess.run(render_cmd, env=os.environ.copy())
            if render_result.returncode == 0:
                print("[runner] HTML report: " + str(html_path))
                if args.open_report:
                    try:
                        if os.name == "nt":
                            os.startfile(str(html_path))  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            subprocess.Popen(["open", str(html_path)])
                        else:
                            subprocess.Popen(["xdg-open", str(html_path)])
                    except Exception as exc:  # pragma: no cover
                        print("[runner] could not open report: " + str(exc))
            else:
                print("[runner] renderer exited " + str(render_result.returncode) +
                      "; HTML report not generated.")

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())





