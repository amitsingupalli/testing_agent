"""Result models, the runner base interface, and the command executor."""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.detect.models import ProjectManifest

ARTIFACT_DIR_NAME = ".testing-agent"
LOG_DIR_NAME = "logs"


class TestType(str, Enum):
    """Kind of test layer being executed."""

    UNIT = "unit"
    INTEGRATION = "integration"
    REGRESSION = "regression"


TestType.__test__ = False  # prevent pytest from trying to collect this class


class FailureInfo(BaseModel):
    """One failing test as reported by the runner's machine-readable output."""

    name: str
    message: str | None = None


class RunResult(BaseModel):
    """Outcome of a single runner execution."""

    runner: str
    test_type: TestType
    manifest_directory: str = ""
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0
    exit_code: int | None = None
    command: str = ""
    success: bool = False
    missing_runner: bool = False
    no_tests: bool = False
    note: str | None = None
    failures: list[FailureInfo] = Field(default_factory=list)

    @property
    def executed(self) -> int:
        """Number of tests that actually ran (excludes skipped)."""
        return self.passed + self.failed + self.errors

    @property
    def pass_rate(self) -> float:
        """Fraction of executed tests that passed; 1.0 when nothing ran."""
        if self.executed == 0:
            return 1.0
        return self.passed / self.executed

    @property
    def verdict(self) -> str:
        if self.missing_runner:
            return "MISSING RUNNER"
        if self.no_tests:
            return "NO TESTS"
        return "PASS" if self.success else "FAIL"


class Runner(ABC):
    """A test runner adapter for one stack."""

    id: str = "unknown"

    @abstractmethod
    def applies(self, manifest: ProjectManifest) -> bool:
        """Whether this adapter can run the given manifest."""

    @abstractmethod
    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
    ) -> RunResult:
        """Execute the suite and return a parsed result."""


def artifact_dir(root: Path) -> Path:
    """Per-project directory for reports, logs, and runner artifacts."""
    return root / ARTIFACT_DIR_NAME


def log_path(root: Path, runner_id: str, test_type: TestType) -> Path:
    """Path of the raw output log for one runner run."""
    logs = artifact_dir(root) / LOG_DIR_NAME
    logs.mkdir(parents=True, exist_ok=True)
    return logs / f"{runner_id}-{test_type.value}.log"


def npm_exec_command(args: list[str]) -> list[str]:
    """Wrap npx-style commands so they work on Windows and POSIX.

    On Windows npx/yarn are .cmd shims, which CreateProcess cannot execute
    directly; going through `cmd /c` fixes that without a shell string.
    """
    import sys

    if sys.platform == "win32" and args and args[0] in ("npx", "npm", "yarn", "pnpm"):
        return ["cmd", "/c", *args]
    return args


def run_command(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
    log_file: Path,
) -> tuple[int | None, int, bool]:
    """Execute a command and write stdout/stderr to a log file.

    Returns (exit_code, duration_ms, missing_runner).
    """
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log_file.write_text(
            f"TIMEOUT after {timeout_seconds}s: {' '.join(command)}\n", encoding="utf-8"
        )
        return 124, int((time.perf_counter() - started) * 1000), False
    except OSError:
        log_file.write_text(
            f"RUNNER NOT FOUND: {' '.join(command)}\n", encoding="utf-8"
        )
        return None, int((time.perf_counter() - started) * 1000), True

    duration_ms = int((time.perf_counter() - started) * 1000)
    content = completed.stdout or ""
    if completed.stderr:
        content += "\n--- stderr ---\n" + completed.stderr
    log_file.write_text(content, encoding="utf-8")
    return completed.returncode, duration_ms, False


def first_existing_directory(manifest_dir: Path, candidates: list[str]) -> str | None:
    """First candidate (relative to the manifest dir) that exists on disk."""
    for candidate in candidates:
        if (manifest_dir / candidate).is_dir():
            return candidate
    return None
