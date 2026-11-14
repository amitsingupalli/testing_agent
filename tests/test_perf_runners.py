"""Tests for performance runner parsers and thresholds."""

from __future__ import annotations

from testing_agent.config import PerformanceConfig
from testing_agent.runners.base import TestType
from testing_agent.runners.perf_autocannon import (
    AutocannonRunner,
    evaluate_performance,
    parse_autocannon_json,
)
from testing_agent.runners.perf_k6 import K6Runner, evaluate_k6, parse_k6_summary
from testing_agent.runners.perf_lighthouse import (
    LighthouseRunner,
    evaluate_lighthouse,
    parse_lighthouse_json,
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


# ---------------------------------------------------------------------------
# k6
# ---------------------------------------------------------------------------


def test_parse_k6_summary_extracts_metrics() -> None:
    text = """
    {
      "metrics": {
        "http_req_duration": {"avg": 4.9, "max": 30, "p(90)": 8, "p(95)": 11.5},
        "http_reqs": {"count": 4000, "rate": 800.5},
        "http_req_failed": {"rate": 0.001}
      }
    }
    """
    summary = parse_k6_summary(text)

    assert summary.parsed is True
    assert summary.latency_p95 == 11.5
    assert summary.requests_per_second == 800.5
    assert summary.errors == 0.001


def test_parse_k6_summary_invalid_or_empty() -> None:
    assert parse_k6_summary("not json").parsed is False
    assert parse_k6_summary("{}").parsed is False
    assert parse_k6_summary('{"metrics": {}}').parsed is True


def test_evaluate_k6_breach_and_ok() -> None:
    breach = parse_k6_summary(
        '{"metrics": {"http_req_duration": {"p(95)": 200}, "http_reqs": {"rate": 50}}}'
    )
    ok, detail = evaluate_k6(breach, PerformanceConfig(max_latency_p975_ms=100))
    assert ok is False
    assert "p95 latency 200ms > 100.0ms" in detail

    fine = parse_k6_summary(
        '{"metrics": {"http_req_duration": {"p(95)": 20}, "http_reqs": {"rate": 900}}}'
    )
    ok2, detail2 = evaluate_k6(fine, PerformanceConfig(max_latency_p975_ms=100))
    assert ok2 is True


def test_k6_runner_applies_to_node_only() -> None:
    from testing_agent.detect.models import ProjectManifest, Stack

    runner = K6Runner()
    assert runner.applies(ProjectManifest(stack=Stack.NODE, test_runner="node"))
    assert not runner.applies(ProjectManifest(stack=Stack.PYTHON, test_runner="pytest"))


def test_k6_runner_skipped_without_script(tmp_path) -> None:
    from testing_agent.detect.models import ProjectManifest, Stack

    result = K6Runner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
    )

    assert result.no_tests is True
    assert "k6_script" in (result.note or "")


def test_k6_runner_missing_binary(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.perf_k6 as module
    from testing_agent.config import ProjectConfig
    from testing_agent.detect.models import ProjectManifest, Stack

    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    config = ProjectConfig(
        root=str(tmp_path), performance=PerformanceConfig(k6_script="load.js")
    )
    result = K6Runner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
        config=config,
    )

    assert result.missing_runner is True
    assert "k6 not found" in (result.note or "")


def test_k6_runner_ok_run(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.perf_k6 as module
    from testing_agent.config import ProjectConfig
    from testing_agent.detect.models import ProjectManifest, Stack

    monkeypatch.setattr(module.shutil, "which", lambda name: "k6.exe")
    (tmp_path / "load.js").write_text("export default function() {}")
    summary_payload = (
        '{"metrics": {"http_req_duration": {"p(95)": 20}, "http_reqs": {"rate": 900}}}'
    )

    def fake_run(command, cwd, timeout, log):
        # the summary-export path IS the log file passed to run_command
        log.write_text(summary_payload)
        return 0, 4000, False

    monkeypatch.setattr(module, "run_command", fake_run)

    config = ProjectConfig(
        root=str(tmp_path),
        performance=PerformanceConfig(k6_script="load.js", max_latency_p975_ms=100),
    )
    result = K6Runner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
        config=config,
    )

    assert result.success is True
    assert result.failed == 0
    assert "p95=20ms" in (result.note or "")


# ---------------------------------------------------------------------------
# lighthouse
# ---------------------------------------------------------------------------


def test_parse_lighthouse_json_extracts_score() -> None:
    text = '{"categories": {"performance": {"score": 0.98}}}'
    summary = parse_lighthouse_json(text)
    assert summary.parsed is True
    assert summary.performance_score == 0.98


def test_parse_lighthouse_json_invalid_or_missing_category() -> None:
    assert parse_lighthouse_json("not json").parsed is False
    assert parse_lighthouse_json("{}").parsed is False
    assert parse_lighthouse_json('{"categories": {"performance": {}}}').parsed is False
    assert parse_lighthouse_json('{"categories": {"seo": {"score": 1.0}}}').parsed is False


def test_evaluate_lighthouse_thresholds() -> None:
    ok, detail = evaluate_lighthouse(
        parse_lighthouse_json('{"categories": {"performance": {"score": 0.9}}}'),
        PerformanceConfig(min_lighthouse_score=80),
    )
    assert ok is True
    assert "90.0/100" in detail

    ok2, detail2 = evaluate_lighthouse(
        parse_lighthouse_json('{"categories": {"performance": {"score": 0.5}}}'),
        PerformanceConfig(min_lighthouse_score=80),
    )
    assert ok2 is False
    assert "below minimum 80" in detail2

    ok3, detail3 = evaluate_lighthouse(
        parse_lighthouse_json('{"categories": {"performance": {"score": 0.5}}}'),
        PerformanceConfig(),
    )
    assert ok3 is True
    assert "no minimum set" in detail3


def test_lighthouse_runner_skipped_by_default(tmp_path) -> None:
    from testing_agent.detect.models import ProjectManifest, Stack

    result = LighthouseRunner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
    )

    assert result.no_tests is True
    assert "run_lighthouse is disabled" in (result.note or "")


def test_lighthouse_runner_missing_binary(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.perf_lighthouse as module
    from testing_agent.config import ProjectConfig
    from testing_agent.detect.models import ProjectManifest, Stack

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    config = ProjectConfig(
        root=str(tmp_path),
        performance=PerformanceConfig(run_lighthouse=True, target_url="http://127.0.0.1:8901"),
    )
    result = LighthouseRunner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=30,
        config=config,
    )

    assert result.missing_runner is True
    assert "npm install -g lighthouse" in (result.note or "")


def test_lighthouse_runner_ok_run(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.perf_lighthouse as module
    from testing_agent.config import ProjectConfig
    from testing_agent.detect.models import ProjectManifest, Stack

    monkeypatch.setattr(module.shutil, "which", lambda name: "lighthouse.cmd")

    def fake_run(command, cwd, timeout, log):
        log.write_text('{"categories": {"performance": {"score": 0.95}}}')
        return 0, 30000, False

    monkeypatch.setattr(module, "run_command", fake_run)

    config = ProjectConfig(
        root=str(tmp_path),
        performance=PerformanceConfig(run_lighthouse=True, target_url="http://127.0.0.1:8901"),
    )
    result = LighthouseRunner().run(
        ProjectManifest(stack=Stack.NODE, test_runner="node"),
        tmp_path,
        TestType.PERFORMANCE,
        timeout_seconds=300,
        config=config,
    )

    assert result.success is True
    assert "95.0/100" in (result.note or "")
