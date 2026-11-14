"""Tests for performance runner parsers and thresholds."""

from __future__ import annotations

from testing_agent.config import PerformanceConfig
from testing_agent.runners.base import TestType
from testing_agent.runners.perf_autocannon import (
    AutocannonRunner,
    evaluate_performance,
    parse_autocannon_json,
)


def test_parse_autocannon_json_extracts_metrics() -> None:
    text = """
    {
      "latency": {"average": 5.1, "p50": 4, "p97_5": 12.4, "max": 40},
      "requests": {"average": 9500.2, "mean": 9500.2, "total": 47500},
      "errors": 2
    }
    """
    summary = parse_autocannon_json(text)

    assert summary.parsed is True
    assert summary.latency_p97_5 == 12.4
    assert summary.latency_max == 40
    assert summary.requests_per_second == 9500.2
    assert summary.errors == 2


def test_parse_autocannon_json_invalid_or_empty() -> None:
    bad = parse_autocannon_json("not json")
    assert bad.parsed is False
    assert parse_autocannon_json("{}").parsed is True
    assert parse_autocannon_json("{}").latency_p97_5 is None


def test_evaluate_performance_ok_with_thresholds() -> None:
    summary = parse_autocannon_json(
        '{"latency": {"p97_5": 90}, "requests": {"average": 1000}, "errors": 0}'
    )
    perf = PerformanceConfig(max_latency_p975_ms=100, min_requests_per_second=500)

    ok, detail = evaluate_performance(summary, perf)

    assert ok is True
    assert "breaches" not in detail


def test_evaluate_performance_latency_breach() -> None:
    summary = parse_autocannon_json('{"latency": {"p97_5": 200}, "requests": {"average": 1000}}')
    perf = PerformanceConfig(max_latency_p975_ms=100)

    ok, detail = evaluate_performance(summary, perf)

    assert ok is False
    assert "p97.5 latency 200ms > 100.0ms" in detail


def test_evaluate_performance_rps_breach() -> None:
    summary = parse_autocannon_json('{"latency": {"p97_5": 10}, "requests": {"average": 100}}')
    perf = PerformanceConfig(min_requests_per_second=500)

    ok, detail = evaluate_performance(summary, perf)

    assert ok is False
    assert "rps 100 < 500" in detail


def test_autocannon_runner_applies_to_node_only() -> None:
    from testing_agent.detect.models import ProjectManifest, Stack

    runner = AutocannonRunner()
    assert runner.applies(ProjectManifest(stack=Stack.NODE, test_runner="node"))
    assert not runner.applies(ProjectManifest(stack=Stack.PYTHON, test_runner="pytest"))


def test_autocannon_runner_skipped_without_target(tmp_path) -> None:
    from testing_agent.detect.models import ProjectManifest, Stack

    result = AutocannonRunner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
    )

    assert result.no_tests is True
    assert "target_url" in (result.note or "")


def test_autocannon_runner_threshold_breach(tmp_path, monkeypatch) -> None:
    import shutil

    import testing_agent.runners.perf_autocannon as module
    from testing_agent.config import ProjectConfig
    from testing_agent.detect.models import ProjectManifest, Stack

    monkeypatch.setattr(module.shutil, "which", shutil.which)

    def fake_run(command, cwd, timeout, log):
        log.write_text('{"latency": {"p97_5": 900}, "requests": {"average": 100}, "errors": 0}')
        return 0, 5500, False

    monkeypatch.setattr(module, "run_command", fake_run)

    manifest = ProjectManifest(stack=Stack.NODE, test_runner="node")
    config = ProjectConfig(
        root=str(tmp_path),
        performance=PerformanceConfig(
            target_url="http://127.0.0.1:8901",
            max_latency_p975_ms=100,
            min_requests_per_second=500,
        ),
    )

    result = AutocannonRunner().run(
        manifest, tmp_path, TestType.PERFORMANCE, timeout_seconds=30, config=config
    )

    assert result.success is False
    assert result.failed == 1
    assert len(result.failures) == 1
    assert "p97.5 latency 900ms > 100.0ms" in (result.note or "")
