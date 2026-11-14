"""Tests for the combined summary section of reports."""

from __future__ import annotations

from testing_agent.report import GateSummary, build_report
from testing_agent.report.markdown_report import render_markdown
from testing_agent.report.terminal import print_terminal
from testing_agent.runners.base import FailureInfo, RunResult, TestType


def make_result(runner: str, test_type: TestType, **overrides) -> RunResult:
    defaults = dict(
        runner=runner,
        test_type=test_type,
        manifest_directory="",
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        duration_ms=100,
        success=True,
    )
    defaults.update(overrides)
    return RunResult(**defaults)


def test_summary_totals_and_by_type() -> None:
    results = [
        make_result("pytest", TestType.UNIT, passed=5),
        make_result("npm-audit", TestType.SECURITY, passed=0, failed=2, success=False),
        make_result(
            "semgrep",
            TestType.SECURITY,
            passed=0,
            failed=0,
            no_tests=True,
            success=False,
        ),
    ]
    report = build_report("target", results, GateSummary(passed=True))

    summary = report["summary"]
    assert summary["total"] == {
        "runners": 2,
        "passed": 5,
        "failed": 2,
        "errors": 0,
        "skipped": 0,
    }
    assert set(summary["by_type"]) == {"unit", "security"}
    assert summary["by_type"]["unit"]["runners"] == ["pytest"]
    assert summary["by_type"]["security"]["runners"] == ["npm-audit"]
    assert summary["by_type"]["security"]["failed"] == 2
    assert summary["active"] is True


def test_summary_inactive_when_only_no_tests() -> None:
    results = [
        make_result("semgrep", TestType.SECURITY, no_tests=True, success=False),
        make_result("none", TestType.SYSTEM, missing_runner=True, success=False),
    ]
    report = build_report("target", results, GateSummary(passed=True))

    summary = report["summary"]
    assert summary["total"]["runners"] == 0
    assert summary["active"] is False


def test_markdown_renders_summary_section() -> None:
    results = [
        make_result("pytest", TestType.UNIT, passed=5),
        make_result("npm-audit", TestType.SECURITY, passed=0, failed=2, success=False),
    ]
    report = build_report("target", results, GateSummary(passed=True))
    markdown = render_markdown(report)

    assert "## Summary" in markdown
    assert "**Runners:** 2 · **Passed:** 5 · **Failed:** 2" in markdown
    assert "`security`: 0 passed / 2 failed / 0 errors (npm-audit)" in markdown
    assert "`unit`: 5 passed / 0 failed / 0 errors (pytest)" in markdown


def test_markdown_no_summary_when_no_results() -> None:
    markdown = render_markdown(build_report("target", [], GateSummary(passed=True)))

    assert "## Summary" not in markdown


def test_terminal_renders_summary(capsys) -> None:
    results = [make_result("pytest", TestType.UNIT, passed=3)]
    report = build_report("target", results, GateSummary(passed=True))

    print_terminal(report)

    output = capsys.readouterr().out
    assert "Summary" in output
    assert "Runners: 1" in output
    assert "unit: 3 passed / 0 failed / 0 errors (pytest)" in output


def test_failures_surface_in_summary_results() -> None:
    results = [
        make_result(
            "npm-audit",
            TestType.SECURITY,
            passed=0,
            failed=1,
            success=False,
            failures=[FailureInfo(name="lodash", message="high: Prototype Pollution")],
        )
    ]
    report = build_report("target", results, GateSummary(passed=False))
    markdown = render_markdown(report)

    assert "## Failures" in markdown
    assert "`npm-audit` — lodash" in markdown
