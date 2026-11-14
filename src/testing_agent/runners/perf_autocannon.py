"""autocannon performance runner (Node projects, HTTP load testing)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.config import PerformanceConfig, ProjectConfig
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


class AutocannonSummary(BaseModel):
    """Parsed autocannon -j output."""

    latency_p97_5: float | None = Field(default=None)
    latency_max: float | None = None
    requests_per_second: float | None = None
    errors: int | None = None
    parsed: bool = False


def parse_autocannon_json(text: str) -> AutocannonSummary:
    """Parse autocannon JSON output (top-level latency/requests/errors)."""
    summary = AutocannonSummary()
    try:
        data = json.loads(text)
    except ValueError:
        return summary

    latency = data.get("latency")
    if isinstance(latency, dict):
        summary.latency_p97_5 = latency.get("p97_5")
        summary.latency_max = latency.get("max")
    requests = data.get("requests")
    if isinstance(requests, dict):
        summary.requests_per_second = requests.get("average")
    summary.errors = data.get("errors")
    summary.parsed = True
    return summary


def evaluate_performance(
    summary: AutocannonSummary,
    performance: PerformanceConfig,
) -> tuple[bool, str]:
    """Return (ok, detail) against configured performance thresholds."""
    breaches: list[str] = []
    if (
        summary.latency_p97_5 is not None
        and performance.max_latency_p975_ms is not None
        and summary.latency_p97_5 > performance.max_latency_p975_ms
    ):
        breaches.append(
            f"p97.5 latency {summary.latency_p97_5}ms > {performance.max_latency_p975_ms}ms"
        )
    if (
        summary.requests_per_second is not None
        and performance.min_requests_per_second is not None
        and summary.requests_per_second < performance.min_requests_per_second
    ):
        breaches.append(
            f"rps {summary.requests_per_second} < {performance.min_requests_per_second}"
        )

    detail = (
        f"p97.5={summary.latency_p97_5}ms, rps={summary.requests_per_second}, "
        f"errors={summary.errors}"
    )
    if breaches:
        detail += " — breaches: " + "; ".join(breaches)
    return not breaches, detail


class AutocannonRunner(Runner):
    """Runs `npx -y autocannon -c N -d N -j <url>` against the target URL."""

    id = "autocannon"

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
        performance = config.performance if config else PerformanceConfig()
        if not performance.target_url:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no performance.target_url configured",
            )

        if shutil.which("npx") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="npx not found on PATH",
            )

        command = npm_exec_command(
            [
                "npx",
                "-y",
                "autocannon",
                "-c",
                str(performance.connections),
                "-d",
                str(performance.duration_seconds),
                "-j",
                performance.target_url,
            ]
        )
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

        summary = parse_autocannon_json(log_file.read_text(encoding="utf-8", errors="replace"))
        if not summary.parsed:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                passed=0,
                failed=1,
                duration_ms=duration_ms,
                exit_code=exit_code,
                command=" ".join(command),
                success=False,
                note=f"autocannon exit {exit_code} — unparseable output",
            )

        ok, detail = evaluate_performance(summary, performance)

        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=1 if ok else 0,
            failed=0 if ok else 1,
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=ok,
            note=f"autocannon exit {exit_code} — {detail}",
            failures=[] if ok else [FailureInfo(name="performance", message=detail)],
        )
