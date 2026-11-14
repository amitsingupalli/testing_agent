"""npm audit security runner (Node projects)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.config import ProjectConfig, SecurityConfig
from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    FailureInfo,
    RunResult,
    Runner,
    TestType,
    log_path,
    npm_exec_command,
    run_command,
)

_MESSAGE_PREVIEW_CHARS = 300


class NpmAuditSummary(BaseModel):
    """Counts from `npm audit --json` output."""

    findings: list[FailureInfo] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    had_error: bool = False


def parse_npm_audit_json(text: str) -> NpmAuditSummary:
    """Parse npm audit JSON (v9+ shape: vulnerabilities dict)."""
    summary = NpmAuditSummary()
    try:
        data = json.loads(text)
    except ValueError:
        return summary

    error = data.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", "unknown"))
        message = str(error.get("summary", "")) or str(error.get("detail", ""))
        summary.had_error = True
        summary.findings.append(
            FailureInfo(name=code, message=f"npm audit failed: {code} — {message}"[:_MESSAGE_PREVIEW_CHARS])
        )
        return summary

    vulnerabilities = data.get("vulnerabilities")
    if not isinstance(vulnerabilities, dict):
        return summary

    for package, info in vulnerabilities.items():
        if not isinstance(info, dict):
            continue
        severity = str(info.get("severity", "unknown"))
        title = str(info.get("title") or info.get("name") or "vulnerability")
        via = info.get("via")
        via_summary = ""
        if isinstance(via, list) and via and isinstance(via[0], dict):
            via_summary = str(via[0].get("title") or "")
        message = f"{severity}: {title}" + (f" ({via_summary})" if via_summary else "")
        summary.findings.append(
            FailureInfo(name=package, message=message[:_MESSAGE_PREVIEW_CHARS])
        )
        summary.severity_counts[severity] = summary.severity_counts.get(severity, 0) + 1
    return summary


def evaluate_thresholds(
    severity_counts: dict[str, int],
    total: int,
    security: SecurityConfig,
) -> tuple[bool, str]:
    """Return (ok, detail) against the configured security thresholds."""
    critical = severity_counts.get("critical", 0)
    high = severity_counts.get("high", 0)
    breaches: list[str] = []
    if critical > security.max_critical:
        breaches.append(f"critical {critical} > {security.max_critical}")
    if high > security.max_high:
        breaches.append(f"high {high} > {security.max_high}")
    if security.max_total is not None and total > security.max_total:
        breaches.append(f"total {total} > {security.max_total}")
    detail = (
        f"critical={critical}, high={high}, total={total}"
        + (f" — breaches: {'; '.join(breaches)}" if breaches else "")
    )
    return not breaches, detail


class NpmAuditRunner(Runner):
    """Runs `npm audit --json` and maps findings to failures."""

    id = "npm-audit"

    def applies(self, manifest: ProjectManifest) -> bool:
        return manifest.stack.value == "node"

    def run(
        self,
        manifest: ProjectManifest,
        root: Path,
        test_type: TestType,
        timeout_seconds: int = 300,
        config: ProjectConfig | None = None,
    ) -> RunResult:
        manifest_dir = (Path(root) / manifest.directory) if manifest.directory else Path(root)
        if not (manifest_dir / "package-lock.json").exists():
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no package-lock.json (npm i --package-lock-only enables audit)",
            )

        command = npm_exec_command(["npm", "audit", "--json"])
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
                note="npm not found on PATH",
            )

        summary = parse_npm_audit_json(log_file.read_text(encoding="utf-8", errors="replace"))
        security = config.security if config else SecurityConfig()
        ok, detail = evaluate_thresholds(summary.severity_counts, len(summary.findings), security)
        if summary.had_error:
            ok = False

        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=0 if summary.findings else 1,
            failed=len(summary.findings),
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=ok,
            note=f"npm audit exit {exit_code} — {detail}",
            failures=summary.findings,
        )
