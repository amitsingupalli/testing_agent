"""Tests for the Playwright compatibility runner (fixture JSON, no live browsers)."""

from __future__ import annotations

from testing_agent.config import CompatibilityConfig, ProjectConfig
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners.base import TestType
from testing_agent.runners.compat_playwright import (
    PlaywrightRunner,
    parse_playwright_json,
)


def node_manifest() -> ProjectManifest:
    return ProjectManifest(stack=Stack.NODE, test_runner="node")


REPORT_JSON = """
{
  "config": {"projects": [{"name": "chromium"}]},
  "suites": [
    {"title": "chromium", "file": "", "specs": [],
     "suites": [
       {"title": "app.spec.ts", "file": "tests/e2e/app.spec.ts", "specs": [
         {"title": "home page loads", "ok": true,
          "tests": [{"status": "expected", "results": [{"status": "passed"}]}]},
         {"title": "checkout rejects empty cart", "ok": false,
          "tests": [{"status": "unexpected",
                     "results": [{"status": "failed",
                                  "error": {"message": "Expected 200 but got 500"}}]}]},
         {"title": "skipped feature", "ok": true,
          "tests": [{"status": "skipped", "results": []}]}
       ]}
     ]}
  ],
  "errors": [],
  "stats": {"startTime": "2026-01-01T00:00:00.000Z", "duration": 12345.0,
            "expected": 2, "unexpected": 1, "flaky": 0, "skipped": 1}
}
"""


def test_parse_playwright_json_stats() -> None:
    summary = parse_playwright_json(REPORT_JSON)

    assert summary.stats.parsed is True
    assert summary.stats.expected == 2
    assert summary.stats.unexpected == 1
    assert summary.stats.flaky == 0
    assert summary.stats.skipped == 1
    assert summary.stats.duration == 12345.0


def test_parse_playwright_json_browsers_and_failures() -> None:
    summary = parse_playwright_json(REPORT_JSON)

    assert summary.browsers == ["chromium"]
    assert len(summary.failures) == 1
    assert summary.failures[0].name == "checkout rejects empty cart"
    assert "Expected 200 but got 500" in (summary.failures[0].message or "")


def test_parse_playwright_json_invalid() -> None:
    bad = parse_playwright_json("not json")
    assert bad.stats.parsed is False
    assert bad.parse_error is not None

    empty = parse_playwright_json("{}")
    assert empty.stats.parsed is False
    assert "no stats" in (empty.parse_error or "")


def test_playwright_runner_applies_to_node_only() -> None:
    runner = PlaywrightRunner()
    assert runner.applies(node_manifest())
    assert not runner.applies(ProjectManifest(stack=Stack.PYTHON, test_runner="pytest"))


def test_playwright_runner_skipped_without_config(tmp_path) -> None:
    result = PlaywrightRunner().run(
        node_manifest(), tmp_path, TestType.COMPATIBILITY, timeout_seconds=30
    )

    assert result.no_tests is True
    assert "playwright.config" in (result.note or "")


def test_playwright_runner_ok_run(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.compat_playwright as module

    (tmp_path / "playwright.config.ts").write_text("export default {}")
    monkeypatch.setattr(module.shutil, "which", lambda name: "npx.cmd")

    captured = {}

    def fake_run(command, cwd, timeout, log, env=None):
        captured["command"] = command
        captured["env"] = env
        log.write_text(REPORT_JSON)
        return 1, 5000, False  # playwright exits 1 when tests fail

    monkeypatch.setattr(module, "run_command", fake_run)

    result = PlaywrightRunner().run(
        node_manifest(), tmp_path, TestType.COMPATIBILITY, timeout_seconds=30
    )

    assert result.passed == 2
    assert result.failed == 1
    assert result.skipped == 1
    assert result.success is False
    assert result.failures[0].name == "checkout rejects empty cart"
    assert "--reporter=json" in captured["command"]


def test_playwright_runner_browser_project_override(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.compat_playwright as module

    (tmp_path / "playwright.config.ts").write_text("export default {}")
    monkeypatch.setattr(module.shutil, "which", lambda name: "npx.cmd")

    captured = {}

    def fake_run(command, cwd, timeout, log, env=None):
        captured["command"] = command
        captured["env"] = env
        log.write_text(REPORT_JSON)
        return 1, 5000, False

    monkeypatch.setattr(module, "run_command", fake_run)

    config = ProjectConfig(
        root=str(tmp_path),
        compatibility=CompatibilityConfig(
            browsers=["chromium", "firefox"], base_url="http://127.0.0.1:8901"
        ),
    )
    result = PlaywrightRunner().run(
        node_manifest(), tmp_path, TestType.COMPATIBILITY, timeout_seconds=30, config=config
    )

    command = captured["command"]
    assert "--project=chromium" in command
    assert "--project=firefox" in command
    assert captured["env"]["PLAYWRIGHT_BASE_URL"] == "http://127.0.0.1:8901"
    assert result.failed == 1


def test_run_command_env_passthrough(tmp_path) -> None:
    import sys

    from testing_agent.runners.base import run_command

    script = "import os; print(os.environ.get('TESTING_AGENT_ENV_PROBE', 'missing'))"
    log = tmp_path / "log.txt"
    code, _, missing = run_command(
        [sys.executable, "-c", script], tmp_path, 30, log, env={"TESTING_AGENT_ENV_PROBE": "hit"}
    )

    assert code == 0
    assert missing is False
    assert "hit" in log.read_text(encoding="utf-8")
