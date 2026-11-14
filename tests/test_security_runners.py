"""Tests for security runner parsers and thresholds."""

from __future__ import annotations

from testing_agent.config import SecurityConfig
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners.base import TestType
from testing_agent.runners.security_bandit import BanditRunner, parse_bandit_json
from testing_agent.runners.security_npm import (
    NpmAuditRunner,
    evaluate_thresholds,
    parse_npm_audit_json,
)
from testing_agent.runners.security_pip import PipAuditRunner, parse_pip_audit_json
from testing_agent.runners.security_semgrep import SemgrepRunner, parse_semgrep_json


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


def test_parse_npm_audit_json_error_payload() -> None:
    summary = parse_npm_audit_json(
        '{"error": {"code": "ENOLOCK", "summary": "requires an existing lockfile."}}'
    )
    assert summary.had_error is True
    assert len(summary.findings) == 1
    assert summary.findings[0].name == "ENOLOCK"
    assert "lockfile" in (summary.findings[0].message or "")


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
    (tmp_path / "package-lock.json").write_text("{}")

    result = NpmAuditRunner().run(
        make_node_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.missing_runner is True
    assert result.success is False


def test_npm_audit_runner_skipped_without_lockfile(tmp_path) -> None:
    result = NpmAuditRunner().run(
        make_node_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.no_tests is True
    assert "package-lock.json" in (result.note or "")


# ---------------------------------------------------------------------------
# pip-audit
# ---------------------------------------------------------------------------


def make_python_manifest() -> ProjectManifest:
    return ProjectManifest(stack=Stack.PYTHON, test_runner="pytest")


def test_parse_pip_audit_json_extracts_findings() -> None:
    text = """
    {
      "dependencies": [
        {"name": "requests", "version": "2.28.0",
         "vulns": [{"id": "GHSA-j8r2-6x86-q33q", "description": "Cookie leak"}]},
        {"name": "flask", "version": "2.0.0", "vulns": []},
        {"name": "jinja2", "version": "3.0.0",
         "vulns": [{"id": "GHSA-h5c8-r9wp-2xm3", "description": "XSS"},
                    {"id": "PYSEC-2023-1", "description": "sandbox escape"}]}
      ]
    }
    """
    findings, total = parse_pip_audit_json(text)

    assert total == 3
    assert findings[0].name == "requests==2.28.0"
    assert "GHSA-j8r2-6x86-q33q" in (findings[0].message or "")
    assert findings[2].name == "jinja2==3.0.0"


def test_parse_pip_audit_json_invalid_or_empty() -> None:
    assert parse_pip_audit_json("not json") == ([], 0)
    assert parse_pip_audit_json("{}") == ([], 0)
    assert parse_pip_audit_json('{"dependencies": []}') == ([], 0)


def test_pip_audit_runner_applies_to_python_only() -> None:
    runner = PipAuditRunner()
    assert runner.applies(make_python_manifest())
    assert not runner.applies(make_node_manifest())


def test_pip_audit_runner_missing_pip_audit(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_pip as module

    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    result = PipAuditRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.missing_runner is True
    assert "pip install pip-audit" in (result.note or "")


def test_pip_audit_runner_thresholds(tmp_path, monkeypatch) -> None:
    """Fake run_command to simulate a pip-audit run reporting one vulnerability."""
    import testing_agent.runners.security_pip as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "pip-audit.exe")

    payload = (
        '{"dependencies": [{"name": "requests", "version": "2.28.0", '
        '"vulns": [{"id": "GHSA-j8r2-6x86-q33q", "description": "Cookie leak"}]}]}'
    )

    def fake_run(command, cwd, timeout, log):
        log.write_text(payload)
        return 0, 1234, False

    monkeypatch.setattr(module, "run_command", fake_run)
    from testing_agent.config import ProjectConfig, SecurityConfig

    result = PipAuditRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )
    assert result.success is False
    assert result.failed == 1
    assert "no total threshold set" in (result.note or "")

    result2 = PipAuditRunner().run(
        make_python_manifest(),
        tmp_path,
        TestType.SECURITY,
        timeout_seconds=30,
        config=ProjectConfig(root=str(tmp_path), security=SecurityConfig(max_total=0)),
    )
    assert result2.success is False
    assert "total 1 > 0" in (result2.note or "")

    result3 = PipAuditRunner().run(
        make_python_manifest(),
        tmp_path,
        TestType.SECURITY,
        timeout_seconds=30,
        config=ProjectConfig(root=str(tmp_path), security=SecurityConfig(max_total=1)),
    )
    assert result3.success is True


# ---------------------------------------------------------------------------
# bandit
# ---------------------------------------------------------------------------


def test_parse_bandit_json_extracts_findings() -> None:
    text = """
    {
      "results": [
        {"filename": "app.py", "line_number": 42, "issue_severity": "HIGH",
         "issue_confidence": "HIGH", "test_id": "B102", "issue_text": "exec used"},
        {"filename": "util.py", "line_number": 7, "issue_severity": "LOW",
         "issue_confidence": "MEDIUM", "test_id": "B101", "issue_text": "assert"}
      ]
    }
    """
    findings, counts = parse_bandit_json(text)

    assert len(findings) == 2
    assert findings[0].name == "app.py:42 [B102]"
    assert "high" in (findings[0].message or "")
    assert "exec used" in (findings[0].message or "")
    assert counts == {"high": 1, "low": 1}


def test_parse_bandit_json_invalid_or_empty() -> None:
    assert parse_bandit_json("not json") == ([], {})
    assert parse_bandit_json("{}") == ([], {})
    assert parse_bandit_json('{"results": []}') == ([], {})


def test_bandit_runner_applies_to_python_only() -> None:
    runner = BanditRunner()
    assert runner.applies(make_python_manifest())
    assert not runner.applies(make_node_manifest())


def test_bandit_runner_missing_binary(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_bandit as module

    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    result = BanditRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.missing_runner is True
    assert "pip install bandit" in (result.note or "")


def test_bandit_runner_threshold_breach(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_bandit as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "bandit.exe")
    payload = (
        '{"results": [{"filename": "app.py", "line_number": 9, "issue_severity": "HIGH", '
        '"issue_confidence": "HIGH", "test_id": "B102", "issue_text": "exec used"}]}'
    )

    def fake_run(command, cwd, timeout, log):
        log.write_text(payload)
        return 0, 500, False

    monkeypatch.setattr(module, "run_command", fake_run)

    result = BanditRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.success is False
    assert result.failed == 1
    assert "high 1 > 0" in (result.note or "")


# ---------------------------------------------------------------------------
# semgrep
# ---------------------------------------------------------------------------


def test_parse_semgrep_json_extracts_findings() -> None:
    text = """
    {
      "results": [
        {"check_id": "python.security.subprocess", "path": "app.py",
         "start": {"line": 10}, "extra": {"message": "subprocess without shell=False"}},
        {"check_id": "generic.secrets", "path": "config.js",
         "start": {"line": 3}, "extra": {"message": "hardcoded secret"}}
      ]
    }
    """
    findings = parse_semgrep_json(text)

    assert len(findings) == 2
    assert findings[0].name == "app.py:10 [python.security.subprocess]"
    assert "subprocess" in (findings[0].message or "")


def test_parse_semgrep_json_invalid_or_empty() -> None:
    assert parse_semgrep_json("not json") == []
    assert parse_semgrep_json("{}") == []
    assert parse_semgrep_json('{"results": []}') == []


def test_semgrep_runner_applies_to_python_and_node() -> None:
    runner = SemgrepRunner()
    assert runner.applies(make_python_manifest())
    assert runner.applies(make_node_manifest())
    assert not runner.applies(ProjectManifest(stack=Stack.GO, test_runner="go test"))


def test_semgrep_runner_skipped_without_rules_or_optin(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_semgrep as module

    monkeypatch.setattr(module.shutil, "which", lambda name: None)

    result = SemgrepRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.no_tests is True
    assert result.missing_runner is False
    assert "skipped" in (result.note or "")


def test_semgrep_runner_runs_with_semyaml_rules(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_semgrep as module

    (tmp_path / ".semgrep.yml").write_text("rules: []")
    monkeypatch.setattr(module.shutil, "which", lambda name: "semgrep.exe")

    captured = {}

    def fake_run(command, cwd, timeout, log):
        captured["command"] = command
        log.write_text('{"results": []}')
        return 0, 250, False

    monkeypatch.setattr(module, "run_command", fake_run)

    result = SemgrepRunner().run(
        make_python_manifest(), tmp_path, TestType.SECURITY, timeout_seconds=30
    )

    assert result.success is True
    assert result.failed == 0
    assert "--config" not in captured["command"]
    assert "auto" not in captured["command"]


def test_semgrep_runner_uses_auto_when_optedin(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.security_semgrep as module

    monkeypatch.setattr(module.shutil, "which", lambda name: "semgrep.exe")

    captured = {}

    def fake_run(command, cwd, timeout, log):
        captured["command"] = command
        log.write_text('{"results": [{"check_id": "c", "path": "a.py", "start": {"line": 1}, "extra": {"message": "m"}}]}')
        return 0, 250, False

    monkeypatch.setattr(module, "run_command", fake_run)
    from testing_agent.config import ProjectConfig, SecurityConfig

    result = SemgrepRunner().run(
        make_python_manifest(),
        tmp_path,
        TestType.SECURITY,
        timeout_seconds=30,
        config=ProjectConfig(root=str(tmp_path), security=SecurityConfig(use_semgrep_auto=True)),
    )

    assert result.success is False
    assert result.failed == 1
    assert captured["command"][2:4] == ["--config", "auto"]
