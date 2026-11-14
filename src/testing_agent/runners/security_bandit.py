"""bandit security runner (Python source scanning)."""

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
from testing_agent.runners.security_npm import evaluate_thresholds

_MESSAGE_PREVIEW_CHARS = 300

DEFAULT_EXCLUDES = "tests,.venv,venv,__pycache__"


def parse_bandit_json(text: str) -> tuple[list[FailureInfo], dict[str, int]]:
    """Parse bandit JSON output into findings and severity counts."""
    findings: list[FailureInfo] = []
    counts: dict[str, int] = {}
    try:
        data = json.loads(text)
    except ValueError:
        return findings, counts

    results = data.get("results")
    if not isinstance(results, list):
        return findings, counts

    for issue in results:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("issue_severity", "UNKNOWN")).lower()
        test_id = str(issue.get("test_id", "B???"))
        filename = str(issue.get("filename", "?"))
        line = issue.get("line_number", "?")
        text_msg = str(issue.get("issue_text", ""))
        findings.append(
            FailureInfo(
                name=f"{filename}:{line} [{test_id}]",
                message=f"{severity}: {text_msg}"[:_MESSAGE_PREVIEW_CHARS],
            )
        )
        counts[severity] = counts.get(severity, 0) + 1
    return findings, counts


class BanditRunner(Runner):
    """Runs `bandit -r <dir> -x <excludes> -f json` against Python sources."""

    id = "bandit"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value == "python"

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: ProjectConfig | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        if shutil.which("bandit") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="bandit not found on PATH (pip install bandit)",
            )

        command = ["bandit", "-r", ".", "-x", DEFAULT_EXCLUDES, "-f", "json", "-q"]
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

        findings, counts = parse_bandit_json(
            log_file.read_text(encoding="utf-8", errors="replace")
        )
        security = config.security if config else SecurityConfig()
        ok, detail = evaluate_thresholds(counts, len(findings), security)

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
            note=f"bandit exit {exit_code} — {detail}",
            failures=findings,
        )
