"""Tests for security runner parsers and thresholds."""

from __future__ import annotations

from testing_agent.config import SecurityConfig
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners.base import TestType
from testing_agent.runners.security_npm import (
    NpmAuditRunner,
    evaluate_thresholds,
    parse_npm_audit_json,
)


def make_node_manifest() -> ProjectManifest:
    return ProjectManifest(directory="", stack=Stack.NODE, test_runner="node")


def test_parse_npm_audit_json_v9_shape() -> None:
    text = """
    {
      "vulnerabilities": {
        "lodash": {
          "name": "lodash",
          "severity": "high",
          "title": "Prototype Pollution",
          "via": [{"title": "Prototype Pollution in lodash"}]
        },
        "minimist": {
          "name": "minimist",
          "severity": "low",
          "title": "Prototype Pollution",
          "via": ["minimist"]
        }
      }
    }
    """
    summary = parse_npm_audit_json(text)

    assert len(summary.findings) == 2
    assert {f.name for f in summary.findings} == {"lodash", "minimist"}
    assert summary.severity_counts == {"high": 1, "low": 1}
    lodash = next(f for f in summary.findings if f.name == "lodash")
    assert "high" in (lodash.message or "")
    assert "Prototype Pollution" in (lodash.message or "")


def test_parse_npm_audit_json_invalid_or_empty() -> None:
    assert parse_npm_audit_json("not json").findings == []
    assert parse_npm_audit_json("{}").findings == []
    assert parse_npm_audit_json('{"vulnerabilities": {}}').findings == []


def test_threshold_defaults_fail_on_critical() -> None:
    ok, detail = evaluate_thresholds({"critical": 1, "high": 0}, 1, SecurityConfig())
    assert ok is False
    assert "critical 1 > 0" in detail


def test_threshold_defaults_pass_on_low_findings() -> None:
    ok, detail = evaluate_thresholds({"low": 3, "moderate": 1}, 4, SecurityConfig())
    assert ok is True
    assert "total=4" in detail


def test_threshold_max_total_breach() -> None:
    config = SecurityConfig(max_total=2)
    ok, detail = evaluate_thresholds({"low": 3}, 3, config)
    assert ok is False
    assert "total 3 > 2" in detail


def test_npm_audit_runner_applies_to_node_only() -> None:
    runner = NpmAuditRunner()
    assert runner.applies(make_node_manifest())
    assert not runner.applies(ProjectManifest(stack=Stack.PYTHON, test_runner="pytest"))


def test_npm_audit_runner_missing_npm(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_npm as module

    monkeypatch.setattr(module, "npm_exec_command", lambda args: ["definitely-missing-binary"])

    result = NpmAuditRunner().run(
        make_node_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.missing_runner is True
    assert result.success is False
