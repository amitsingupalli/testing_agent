"""Lighthouse performance runner (opt-in; heavy Chrome dependency)."""

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


class LighthouseSummary(BaseModel):
    """Parsed lighthouse JSON output (performance category)."""

    performance_score: float | None = None  # 0..1 from lighthouse
    parsed: bool = False


def parse_lighthouse_json(text: str) -> LighthouseSummary:
    """Parse lighthouse JSON output; extract categories.performance.score."""
    summary = LighthouseSummary()
    try:
        data = json.loads(text)
    except ValueError:
        return summary

    categories = data.get("categories")
    if not isinstance(categories, dict):
        return summary

    performance = categories.get("performance")
    if not isinstance(performance, dict):
        return summary

    score = performance.get("score")
    if isinstance(score, (int, float)):
        summary.performance_score = float(score)
        summary.parsed = True
    return summary


def evaluate_lighthouse(
    summary: LighthouseSummary,
    performance: PerformanceConfig,
) -> tuple[bool, str]:
    """Return (ok, detail) against min_lighthouse_score (0-100 scale)."""
    score_100 = None if summary.performance_score is None else summary.performance_score * 100
    if performance.min_lighthouse_score is not None:
        ok = score_100 is not None and score_100 >= performance.min_lighthouse_score
        detail = f"lighthouse score={score_100:.1f}/100"
        if not ok:
            detail += f" — below minimum {performance.min_lighthouse_score}"
    else:
        ok = True
        detail = f"lighthouse score={score_100:.1f}/100 (no minimum set)"
    return ok, detail


class LighthouseRunner(Runner):
    """Runs `lighthouse <url> --output=json --quiet` when explicitly enabled."""

    id = "lighthouse"

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

        if not performance.run_lighthouse:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: run_lighthouse is disabled",
            )
        if not performance.target_url:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no performance.target_url configured",
            )

        if shutil.which("lighthouse") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="lighthouse not found on PATH (npm install -g lighthouse)",
            )

        log_file = log_path(manifest_dir, self.id, test_type)
        command = [
            "lighthouse",
            performance.target_url,
            "--output=json",
            "--quiet",
            "--chrome-flags=--headless",
        ]
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

        summary = parse_lighthouse_json(log_file.read_text(encoding="utf-8", errors="replace"))
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
                note=f"lighthouse exit {exit_code} — unparseable output",
            )

        ok, detail = evaluate_lighthouse(summary, performance)

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
            note=f"lighthouse exit {exit_code} — {detail}",
            failures=[] if ok else [FailureInfo(name="performance", message=detail)],
        )
