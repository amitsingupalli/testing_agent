"""opencode CLI backend: delegate generation to `opencode run`."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from testing_agent.generate.backends import Backend, GenerationError
from testing_agent.generate.models import GenerationTarget
from testing_agent.generate.prompts import build_opencode_prompt, extract_code_block


def _wrap_windows_shim(args: list[str]) -> list[str]:
    """cmd /c wrapper for .cmd shims (opencode on Windows via npm)."""
    if sys.platform == "win32":
        return ["cmd", "/c", *args]
    return args


class OpenCodeBackend(Backend):
    """Runs `opencode run <prompt>` in the project — opencode's agent
    reads the repo itself and writes the test file."""

    id = "opencode"
    writes_files = True  # the opencode agent writes the test file itself

    def __init__(self, executable: str = "opencode") -> None:
        self._executable = executable

    def is_available(self) -> bool:
        return shutil.which(self._executable) is not None

    def generate(
        self,
        root: Path,
        target: GenerationTarget,
        framework: str,
        timeout_seconds: int,
        failure_feedback: str | None = None,
    ) -> str:
        prompt = build_opencode_prompt(root, target, framework, failure_feedback)
        command = _wrap_windows_shim([self._executable, "run", prompt])
        try:
            completed = subprocess.run(
                command,
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise GenerationError(f"opencode run timed out after {timeout_seconds}s") from error
        except OSError as error:
            raise GenerationError(f"could not execute opencode: {error}") from error

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise GenerationError(f"opencode run failed (exit {completed.returncode}): {detail[:500]}")

        code = extract_code_block(completed.stdout or "")
        if not code.strip():
            raise GenerationError("opencode run produced no code output")
        return code
