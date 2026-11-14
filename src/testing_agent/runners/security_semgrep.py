"""semgrep security runner (optional; requires .semgrep.yml or opt-in auto config)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from testing_agent.config import ProjectConfig, SecurityConfig
from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    FailureInfo,
    RunResult,
    Runner,
    TestType,
    log_path,
    run_command,
)

_MESSAGE_PREVIEW_CHARS = 300


def parse_semgrep_json(text: str) -> list[FailureInfo]:
    """Parse semgrep JSON output into findings."""
    findings: list[FailureInfo] = []
    try:
        data = json.loads(text)
    except ValueError:
        return findings

    results = data.get("results")
    if not isinstance(results, list):
        return findings

    for issue in results:
        if not isinstance(issue, dict):
            continue
        check_id = str(issue.get("check_id", "?"))
        path = str(issue.get("path", "?"))
        start = issue.get("start") or {}
        line = start.get("line", "?") if isinstance(start, dict) else "?"
        extra = issue.get("extra") or {}
        message = str(extra.get("message", "")) if isinstance(extra, dict) else ""
        findings.append(
            FailureInfo(
                name=f"{path}:{line} [{check_id}]",
                message=message[:_MESSAGE_PREVIEW_CHARS],
            )
        )
    return findings


class SemgrepRunner(Runner):
    """Runs `semgrep scan --json` when the project opts into semgrep scanning."""

    id = "semgrep"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value in ("python", "node")

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: ProjectConfig | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        security = config.security if config else SecurityConfig()
        has_rules = (manifest_dir / ".semgrep.yml").exists()
        use_auto = security.use_semgrep_auto

        if not has_rules and not use_auto:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no .semgrep.yml and use_semgrep_auto is disabled",
            )

        if shutil.which("semgrep") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="semgrep not found on PATH (pip install semgrep)",
            )

        command = ["semgrep", "scan"]
        if not has_rules and use_auto:
            command += ["--config", "auto"]
        command += ["--json", "-q", "--exclude", "tests,.venv,venv,node_modules"]

        log_file = log_path(manifest_dir, self.id, test_type)
        exit_code, duration_ms, missing = run_command(
            command, manifest_dir, timeout_seconds, log_file
        )
        if missing:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
            )

        findings = parse_semgrep_json(log_file.read_text(encoding="utf-8", errors="replace"))
        ok = not findings

        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=0 if findings else 1,
            failed=len(findings),
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=ok,
            note=f"semgrep exit {exit_code} — findings={len(findings)}",
            failures=findings,
        )
