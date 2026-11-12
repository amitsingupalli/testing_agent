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
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        suite_dir = self._suite_dir(manifest_dir, test_type)
        if suite_dir is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note=f"no test directory found in '{manifest.directory or '.'}'",
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
            suite_dir,
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
