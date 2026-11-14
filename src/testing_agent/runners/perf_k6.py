"""k6 performance runner (via k6 --summary-export)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel

from testing_agent.config import PerformanceConfig, ProjectConfig
from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import (
    FailureInfo,
    RunResult,
    Runner,
    TestType,
    log_path,
    run_command,
)


class K6Summary(BaseModel):
    """Parsed k6 --summary-export output."""

    latency_p95: float | None = None
    requests_per_second: float | None = None
    errors: float | None = None  # http_req_failed rate (0..1)
    parsed: bool = False


def parse_k6_summary(text: str) -> K6Summary:
    """Parse k6 summary-export JSON (metrics.http_req_duration / http_reqs)."""
    summary = K6Summary()
    try:
        data = json.loads(text)
    except ValueError:
        return summary

    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return summary

    duration = metrics.get("http_req_duration")
    if isinstance(duration, dict):
        summary.latency_p95 = duration.get("p(95)")
    reqs = metrics.get("http_reqs")
    if isinstance(reqs, dict):
        summary.requests_per_second = reqs.get("rate")
    failed = metrics.get("http_req_failed")
    if isinstance(failed, dict):
        summary.errors = failed.get("rate")
    summary.parsed = True
    return summary


def evaluate_k6(
    summary: K6Summary,
    performance: PerformanceConfig,
) -> tuple[bool, str]:
    """Return (ok, detail) against configured thresholds (k6 p95 latency)."""
    breaches: list[str] = []
    if (
        summary.latency_p95 is not None
        and performance.max_latency_p975_ms is not None
        and summary.latency_p95 > performance.max_latency_p975_ms
    ):
        breaches.append(
            f"p95 latency {summary.latency_p95}ms > {performance.max_latency_p975_ms}ms"
        )
    if (
        summary.requests_per_second is not None
        and performance.min_requests_per_second is not None
        and summary.requests_per_second < performance.min_requests_per_second
    ):
        breaches.append(
            f"rps {summary.requests_per_second} < {performance.min_requests_per_second}"
        )

    detail = f"p95={summary.latency_p95}ms, rps={summary.requests_per_second}"
    if breaches:
        detail += " — breaches: " + "; ".join(breaches)
    return not breaches, detail


class K6Runner(Runner):
    """Runs `k6 run --summary-export <tmp> <script>` when a k6 script is configured."""

    id = "k6"

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
        script = performance.k6_script

        if not script:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no performance.k6_script configured",
            )

        if shutil.which("k6") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="k6 not found on PATH",
            )

        log_file = log_path(manifest_dir, self.id, test_type)
        command = ["k6", "run", "--summary-export", str(log_file), str(script)]
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

        summary = parse_k6_summary(log_file.read_text(encoding="utf-8", errors="replace"))
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
                note=f"k6 exit {exit_code} — unparseable summary output",
            )

        ok, detail = evaluate_k6(summary, performance)

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
            note=f"k6 exit {exit_code} — {detail}",
            failures=[] if ok else [FailureInfo(name="performance", message=detail)],
        )
