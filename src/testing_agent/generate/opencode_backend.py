"""opencode CLI backend: delegate generation to `opencode run`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from testing_agent.generate.backends import Backend, GenerationError
from testing_agent.generate.models import GenerationTarget
from testing_agent.generate.prompts import build_generation_prompt, extract_code_block


class OpenCodeBackend(Backend):
    """Runs `opencode run <prompt>` in the project — opencode's agent
    reads the repo itself and writes the test file."""

    id = "opencode"

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
        prompt = build_generation_prompt(root, target, framework, failure_feedback)
        try:
            completed = subprocess.run(
                [self._executable, "run", prompt],
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
