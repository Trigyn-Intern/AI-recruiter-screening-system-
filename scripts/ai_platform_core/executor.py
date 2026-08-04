"""Optional Codex CLI runner with graceful fallback.

Codex CLI exposes a non-interactive `codex exec` subcommand (alias `e`)
that takes the prompt as a positional argument or via stdin. This module
pipes the prompt through stdin, points CODEX_HOME at a local runtime
folder, and routes codex to a local Ollama provider (no external API).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CODEX_CANDIDATES = ("codex", "codex.cmd", "codex.exe", "codex.bat")

CREATE_NO_WINDOW = 0x08000000

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CODEX_HOME = REPO_ROOT / ".ai" / "runtime" / "codex_home"
DEFAULT_OSS_MODEL = "llama3.2"


def _resolve_codex_binary() -> str | None:
    for candidate in CODEX_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        for name in CODEX_CANDIDATES:
            candidate = Path(local_appdata) / "Programs" / "codex" / name
            if candidate.exists():
                return str(candidate)
    return None


def _is_windows_shim(path: str) -> bool:
    lower = path.lower()
    return lower.endswith((".cmd", ".bat"))


def _cmd_quote(value: str) -> str:
    if not value:
        return '""'
    needs_quote = False
    for ch in value:
        if ch in (" ", "\t", "&", "^", "|", "<", ">", "(", ")"):
            needs_quote = True
            break
    if needs_quote:
        return '"' + value.replace('"', '""') + '"'
    return value


@dataclass(frozen=True)
class CodexRunner:
    extra_flags: tuple[str, ...] = (
        "--skip-git-repo-check",
        "--ephemeral",
        "--oss",
        "--local-provider",
        "ollama",
    )
    working_directory: Path | None = None
    codex_home: Path | None = None
    oss_model: str = DEFAULT_OSS_MODEL
    timeout_seconds: int = 1800

    def _binary(self) -> str | None:
        return _resolve_codex_binary()

    def is_available(self) -> bool:
        return self._binary() is not None

    def binary_name(self) -> str:
        return self._binary() or "codex"

    def manual_command(self, prompt_file: Path) -> str:
        binary = self.binary_name()
        flags = " ".join(self.extra_flags)
        if self.oss_model:
            flags += f" --model {_cmd_quote(self.oss_model)}"
        return f"{binary} exec {flags} < {_cmd_quote(str(prompt_file))}".strip()

    def _shim_command_line(self) -> str:
        binary = self._binary() or "codex"
        parts: list[str] = [_cmd_quote(binary), "exec"]
        for flag in self.extra_flags:
            parts.append(_cmd_quote(flag))
        if self.oss_model:
            parts.extend(["--model", _cmd_quote(self.oss_model)])
        return " ".join(parts)

    def _build_invocation(self) -> tuple[list[str], dict[str, Any]]:
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "bufsize": 1,
        }
        if self.working_directory is not None:
            popen_kwargs["cwd"] = str(self.working_directory)
        if os.name == "nt":
            popen_kwargs["creationflags"] = CREATE_NO_WINDOW

        binary = self._binary() or "codex"
        if os.name == "nt" and _is_windows_shim(binary):
            cmd = os.environ.get("COMSPEC", "cmd.exe")
            argv = [cmd, "/D", "/S", "/C", self._shim_command_line()]
        else:
            argv = [binary, "exec", *self.extra_flags]
            if self.oss_model:
                argv.extend(["--model", self.oss_model])
        return argv, popen_kwargs

    def _prepare_env(self) -> dict[str, str]:
        """Return an env dict that points CODEX_HOME at a writable local folder."""

        env = os.environ.copy()
        target = self.codex_home or DEFAULT_CODEX_HOME
        target.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(target)
        env.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")
        if self.oss_model:
            env["CODEX_OSS_MODEL"] = self.oss_model
        env.setdefault("NO_COLOR", "1")
        return env

    def _read_prompt(self, prompt_file: Path) -> str:
        try:
            return prompt_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            raise RuntimeError(f"could not read prompt file: {exc}") from exc

    def run(self, prompt_file: Path) -> dict[str, Any]:
        binary = self._binary()
        if binary is None:
            return {
                "status": "skipped",
                "reason": "codex CLI not detected on PATH",
                "returncode": None,
                "duration_seconds": 0.0,
                "stdout_path": None,
                "stderr_path": None,
                "manual_command": self.manual_command(prompt_file),
            }

        try:
            prompt_text = self._read_prompt(prompt_file)
        except RuntimeError as exc:
            return {
                "status": "failed",
                "reason": str(exc),
                "returncode": None,
                "duration_seconds": 0.0,
                "stdout_path": None,
                "stderr_path": None,
                "manual_command": self.manual_command(prompt_file),
            }

        argv, popen_kwargs = self._build_invocation()
        popen_kwargs["env"] = self._prepare_env()
        start = time.monotonic()
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(argv, **popen_kwargs)
        except FileNotFoundError as exc:
            return {
                "status": "skipped",
                "reason": f"codex binary disappeared before launch: {exc}",
                "returncode": None,
                "duration_seconds": round(time.monotonic() - start, 2),
                "stdout_path": None,
                "stderr_path": None,
                "manual_command": self.manual_command(prompt_file),
            }
        except OSError as exc:
            return {
                "status": "failed",
                "reason": f"could not launch codex: {exc}",
                "returncode": None,
                "duration_seconds": round(time.monotonic() - start, 2),
                "stdout_path": None,
                "stderr_path": None,
                "manual_command": self.manual_command(prompt_file),
            }

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        timed_out = False

        try:
            remaining = max(1, self.timeout_seconds - int(time.monotonic() - start))
            stdout_text, stderr_text = process.communicate(
                input=prompt_text, timeout=remaining
            )
            stdout_chunks.append(stdout_text)
            stderr_chunks.append(stderr_text)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = process.wait()
        except Exception as exc:  # noqa: BLE001
            stderr_chunks.append(f"\n[executor] stream error: {exc}\n")
            returncode = process.poll()

        duration = round(time.monotonic() - start, 2)
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        stdout_path = prompt_file.parent / "codex_stdout.log"
        stderr_path = prompt_file.parent / "codex_stderr.log"
        stdout_path.write_text(stdout_text, encoding="utf-8", errors="ignore")
        stderr_path.write_text(stderr_text, encoding="utf-8", errors="ignore")

        if timed_out:
            return {
                "status": "timeout",
                "reason": f"codex exceeded {self.timeout_seconds}s",
                "returncode": returncode,
                "duration_seconds": duration,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "manual_command": None,
            }

        return {
            "status": "ok" if returncode == 0 else "failed",
            "reason": None,
            "returncode": returncode,
            "duration_seconds": duration,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "manual_command": None,
        }
