"""jest adapter (Node projects using jest)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    FailureInfo,
    RunResult,
    Runner,
    TestType,
    artifact_dir,
    first_existing_directory,
    log_path,
    npm_exec_command,
    run_command,
)

_INTEGRATION_DIRS = ["tests/integration", "test/integration", "e2e"]
_MESSAGE_PREVIEW_CHARS = 500


class JestSummary(BaseModel):
    """Counts from jest's --json aggregate output."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[FailureInfo] = Field(default_factory=list)


def parse_jest_json(json_path: Path) -> JestSummary:
    """Parse jest's aggregate JSON file into counts and failures."""
    summary = JestSummary()
    try:
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return summary

    for test_file in data.get("testResults") or []:
        for assertion in test_file.get("assertionResults") or []:
            status = assertion.get("status")
            name = assertion.get("fullName") or assertion.get("title") or "<unnamed>"
            if status == "passed":
                summary.passed += 1
            elif status in ("failed", "timedOut"):
                summary.failed += 1
                message = next(
                    (str(m) for m in (assertion.get("failureMessages") or []) if m), None
                )
                if message and len(message) > _MESSAGE_PREVIEW_CHARS:
                    message = message[:_MESSAGE_PREVIEW_CHARS] + "..."
                summary.failures.append(FailureInfo(name=name, message=message))
            elif status in ("pending", "skipped", "todo"):
                summary.skipped += 1
    return summary


class JestRunner(Runner):
    """Runs jest with aggregate JSON output via npx."""

    id = "jest"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value == "node" and manifest.test_runner == "jest"

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
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

        result_file = artifact_dir(manifest_dir) / f"jest-{test_type.value}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        command = npm_exec_command(
            ["npx", "jest", *target_args, "--json", f"--outputFile={result_file}"]
        )
        log_file = log_path(manifest_dir, self.id, test_type)
        exit_code, duration_ms, missing = run_command(
            command, manifest_dir, timeout_seconds, log_file
        )

        summary = parse_jest_json(result_file) if result_file.is_file() else None
        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=summary.passed if summary else 0,
            failed=summary.failed if summary else 0,
            skipped=summary.skipped if summary else 0,
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=(missing is False and exit_code == 0),
            missing_runner=missing,
            failures=summary.failures if summary else [],
        )
