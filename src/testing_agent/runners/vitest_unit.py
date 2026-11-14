"""vitest adapter (Node projects using vitest)."""

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
    npm_exec_command,
    run_command,
)
from testing_agent.runners.junit import parse_junit

_INTEGRATION_DIRS = ["tests/integration", "test/integration", "e2e"]


class VitestRunner(Runner):
    """Runs vitest with JUnit XML output via npx."""

    id = "vitest"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value == "node" and manifest.test_runner == "vitest"

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: object | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        target_args: list[str] = []
        if test_type == TestType.INTEGRATION:
            integration_dir = first_existing_directory(manifest_dir, _INTEGRATION_DIRS)
            if integration_dir is None:
                return RunResult(
                    runner=self.id,
                    test_type=test_type,
                    manifest_directory=manifest.directory,
                    no_tests=True,
                    note="no integration test directory found",
                )
            target_args = [integration_dir]

        junit_file = artifact_dir(manifest_dir) / f"vitest-{test_type.value}.xml"
        junit_file.parent.mkdir(parents=True, exist_ok=True)
        command = npm_exec_command(
            [
                "npx",
                "vitest",
                "run",
                *target_args,
                "--reporter=junit",
                f"--outputFile={junit_file}",
            ]
        )
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
