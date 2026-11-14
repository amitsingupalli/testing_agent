"""pip-audit security runner (Python projects)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from testing_agent.config import ProjectConfig
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


def parse_pip_audit_json(text: str) -> tuple[list[FailureInfo], int]:
    """Parse pip-audit JSON into findings; returns (findings, total)."""
    findings: list[FailureInfo] = []
    try:
        data = json.loads(text)
    except ValueError:
        return findings, 0

    dependencies = data.get("dependencies")
    if not isinstance(dependencies, list):
        return findings, 0

    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        name = str(dependency.get("name", "?"))
        version = str(dependency.get("version", "?"))
        vulns = dependency.get("vulns") or []
        if not isinstance(vulns, list):
            continue
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            vuln_id = str(vuln.get("id", "unknown"))
            description = str(vuln.get("description", "") or vuln.get("fix_versions", ""))
            findings.append(
                FailureInfo(
                    name=f"{name}=={version}",
                    message=f"{vuln_id}: {description}"[:_MESSAGE_PREVIEW_CHARS],
                )
            )
    return findings, len(findings)


class PipAuditRunner(Runner):
    """Runs `pip-audit -f json` (requires pip-audit on PATH)."""

    id = "pip-audit"

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
        if shutil.which("pip-audit") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="pip-audit not found on PATH (pip install pip-audit)",
            )

        command = ["pip-audit", "-f", "json"]
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

        findings, total = parse_pip_audit_json(
            log_file.read_text(encoding="utf-8", errors="replace")
        )
        security = config.security if config else None
        if security is None:
            from testing_agent.config import SecurityConfig

            security = SecurityConfig()
        # pip-audit JSON has no severity levels; only the total threshold applies.
        max_total = security.max_total
        if max_total is None:
            ok = not findings
            detail = f"vulnerabilities={total} (no total threshold set)"
        else:
            ok = total <= max_total
            detail = f"vulnerabilities={total}"
            if not ok:
                detail += f" — total {total} > {max_total}"

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
            note=f"pip-audit exit {exit_code} — {detail}",
            failures=findings,
        )
