"""Adapter for Node's built-in test runner (`node --test`)."""

from __future__ import annotations

from pathlib import Path

from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    RunResult,
    Runner,
    TestType,
    artifact_dir,
    first_existing_directory,
    log_path,
    run_command,
)
from testing_agent.runners.junit import parse_junit

_UNIT_DIRS = ["tests/unit", "tests", "test"]
_INTEGRATION_DIRS = ["tests/integration", "test/integration"]
_TEST_FILE_PATTERNS = ("*.test.js", "*.test.mjs", "*.test.cjs", "test.js", "test.mjs", "test.cjs")


def _collect_test_files(suite_dir: Path) -> list[Path]:
    """Expand a suite directory into concrete test files.

    Node's --test accepts file paths but (on some versions/platforms,
    including Node 24 on Windows) rejects directories, so we expand here.
    """
    files: set[Path] = set()
    for pattern in _TEST_FILE_PATTERNS:
        files.update(suite_dir.glob(pattern))
        files.update(suite_dir.glob(f"**/{pattern}"))
    return sorted(files)


class NodeTestRunner(Runner):
    """Runs Node's built-in test runner with the junit reporter (zero installs)."""

    id = "node"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value == "node" and manifest.test_runner == "node"

    def _suite_dir(self, manifest_dir: Path, test_type: TestType) -> str | None:
        if test_type == TestType.INTEGRATION:
            return first_existing_directory(manifest_dir, _INTEGRATION_DIRS)
        return first_existing_directory(manifest_dir, _UNIT_DIRS)

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: object | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        suite_dir_name = self._suite_dir(manifest_dir, test_type)
        if suite_dir_name is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note=f"no test directory found in '{manifest.directory or '.'}'",
            )

        suite_dir = manifest_dir / suite_dir_name
        test_files = _collect_test_files(suite_dir)
        if not test_files:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note=f"no *.test.* files found under '{suite_dir_name}'",
            )

        junit_file = artifact_dir(manifest_dir) / f"node-{test_type.value}.xml"
        junit_file.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "node",
            "--test",
            "--test-reporter",
            "junit",
            "--test-reporter-destination",
            str(junit_file),
            *[str(path.relative_to(manifest_dir)) for path in test_files],
        ]
        log_file = log_path(manifest_dir, self.id, test_type)
        exit_code, duration_ms, missing = run_command(
            command, manifest_dir, timeout_seconds, log_file
        )

        summary = parse_junit(junit_file) if junit_file.is_file() else None
        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=summary.passed if summary else 0,
            failed=summary.failed if summary else 0,
            errors=summary.errors if summary else 0,
            skipped=summary.skipped if summary else 0,
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=(missing is False and exit_code == 0),
            missing_runner=missing,
            failures=summary.failures if summary else [],
        )
