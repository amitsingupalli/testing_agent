"""Playwright compatibility runner (browser matrix via @playwright/test)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.config import CompatibilityConfig, ProjectConfig
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

_PLAYWRIGHT_CONFIG_NAMES = (
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
)

_MESSAGE_PREVIEW_CHARS = 300


class PlaywrightStats(BaseModel):
    """Stats block of the Playwright JSON report."""

    expected: int = 0
    unexpected: int = 0
    flaky: int = 0
    skipped: int = 0
    duration: float = 0.0
    parsed: bool = False


class PlaywrightSummary(BaseModel):
    """Parsed Playwright JSON report."""

    stats: PlaywrightStats = Field(default_factory=PlaywrightStats)
    browsers: list[str] = Field(default_factory=list)
    failures: list[FailureInfo] = Field(default_factory=list)
    parse_error: str | None = None


def _walk_suites(
    suites: list[dict],
    browsers: list[str],
    failures: list[FailureInfo],
    depth: int = 0,
) -> None:
    """Recursively collect browser names and failed spec titles."""
    if depth > 10:
        return
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        title = suite.get("title")
        # top-level suites are named after the config project (browser)
        if isinstance(title, str) and title and depth == 0:
            browsers.append(title)
        specs = suite.get("specs")
        if isinstance(specs, list):
            for spec in specs:
                if not isinstance(spec, dict):
                    continue
                spec_title = str(spec.get("title", "?"))
                ok = spec.get("ok")
                tests = spec.get("tests")
                failed_result = None
                if isinstance(tests, list):
                    for test in tests:
                        if not isinstance(test, dict):
                            continue
                        if test.get("status") == "unexpected":
                            for result in test.get("results") or []:
                                if isinstance(result, dict) and result.get("error"):
                                    failed_result = result
                                    break
                            break
                if ok is False or failed_result is not None:
                    message = None
                    if failed_result and isinstance(failed_result.get("error"), dict):
                        message = str(failed_result["error"].get("message", ""))[
                            :_MESSAGE_PREVIEW_CHARS
                        ]
                    failures.append(FailureInfo(name=spec_title, message=message))
        inner = suite.get("suites")
        if isinstance(inner, list):
            _walk_suites(inner, browsers, failures, depth + 1)


def parse_playwright_json(text: str) -> PlaywrightSummary:
    """Parse `npx playwright test --reporter=json` output."""
    summary = PlaywrightSummary()
    try:
        data = json.loads(text)
    except ValueError as exc:
        summary.parse_error = f"unparseable JSON report: {exc}"
        return summary

    if not isinstance(data, dict) or not isinstance(data.get("stats"), dict):
        summary.parse_error = "report has no stats block"
        return summary

    stats = data["stats"]
    summary.stats = PlaywrightStats(
        expected=int(stats.get("expected", 0) or 0),
        unexpected=int(stats.get("unexpected", 0) or 0),
        flaky=int(stats.get("flaky", 0) or 0),
        skipped=int(stats.get("skipped", 0) or 0),
        duration=float(stats.get("duration", 0.0) or 0.0),
        parsed=True,
    )
    suites = data.get("suites")
    if isinstance(suites, list):
        _walk_suites(suites, summary.browsers, summary.failures)
    return summary


class PlaywrightRunner(Runner):
    """Runs the Playwright browser matrix when a playwright config is present."""

    id = "playwright"

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
        compatibility = config.compatibility if config else CompatibilityConfig()

        has_config = any((manifest_dir / name).is_file() for name in _PLAYWRIGHT_CONFIG_NAMES)
        if not has_config:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                no_tests=True,
                note="skipped: no playwright.config.* in this project",
            )

        if shutil.which("npx") is None:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
                note="npx not found on PATH",
            )

        command = npm_exec_command(["npx", "-y", "playwright", "test", "--reporter=json"])
        for browser in compatibility.browsers:
            command.append(f"--project={browser}")

        env = {"PLAYWRIGHT_JSON_OUTPUT_NAME": "-", "PLAYWRIGHT_JSON_OUTPUT_LINE": "0"}
        if compatibility.base_url:
            env["PLAYWRIGHT_BASE_URL"] = compatibility.base_url

        log_file = log_path(manifest_dir, self.id, test_type)
        exit_code, duration_ms, missing = run_command(
            command, manifest_dir, compatibility.timeout_seconds, log_file, env=env
        )
        if missing:
            return RunResult(
                runner=self.id,
                test_type=test_type,
                manifest_directory=manifest.directory,
                missing_runner=True,
            )

        # opt-in browser installation for missing engines
        if exit_code not in (0, 1) and compatibility.install_if_missing and compatibility.browsers:
            install_cmd = npm_exec_command(
                ["npx", "-y", "playwright", "install", *compatibility.browsers]
            )
            run_command(install_cmd, manifest_dir, compatibility.timeout_seconds, log_file)
            exit_code, duration_ms, missing = run_command(
                command, manifest_dir, compatibility.timeout_seconds, log_file, env=env
            )
            if missing:
                return RunResult(
                    runner=self.id,
                    test_type=test_type,
                    manifest_directory=manifest.directory,
                    missing_runner=True,
                )

        summary = parse_playwright_json(log_file.read_text(encoding="utf-8", errors="replace"))
        if not summary.stats.parsed:
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
                note=(
                    f"playwright exit {exit_code} — {summary.parse_error} "
                    "(is @playwright/test installed? npm i -D @playwright/test)"
                ),
            )

        stats = summary.stats
        browsers = f" browsers=[{','.join(summary.browsers)}]" if summary.browsers else ""
        ok = stats.unexpected == 0 and summary.parse_error is None
        detail = (
            f"expected={stats.expected}, unexpected={stats.unexpected}, "
            f"flaky={stats.flaky}, skipped={stats.skipped}{browsers}"
        )

        return RunResult(
            runner=self.id,
            test_type=test_type,
            manifest_directory=manifest.directory,
            passed=stats.expected,
            failed=stats.unexpected,
            errors=0,
            skipped=stats.skipped,
            duration_ms=duration_ms,
            exit_code=exit_code,
            command=" ".join(command),
            success=ok,
            note=f"playwright exit {exit_code} — {detail}",
            failures=summary.failures,
        )
