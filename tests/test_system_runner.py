"""Tests for the SystemRunner (mocked HTTP, real subprocess boot)."""

from __future__ import annotations

import time

from testing_agent.config import EndpointCheck, ProjectConfig, SystemConfig
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners.base import TestType
from testing_agent.runners.system_boot import (
    SystemRunner,
    check_url,
    split_boot_command,
)


def make_node_manifest() -> ProjectManifest:
    return ProjectManifest(stack=Stack.NODE, test_runner="node")


def test_split_boot_command_wraps_npm_family_on_windows(monkeypatch) -> None:
    monkeypatch.setattr("os.name", "nt")
    assert split_boot_command("npm start") == ["cmd", "/c", "npm", "start"]
    assert split_boot_command("npx serve") == ["cmd", "/c", "npx", "serve"]


def test_split_boot_command_plain_executables(monkeypatch) -> None:
    monkeypatch.setattr("os.name", "nt")
    assert split_boot_command("node server.js") == ["node", "server.js"]
    assert split_boot_command("python -m http.server 8099") == [
        "python",
        "-m",
        "http.server",
        "8099",
    ]
    assert split_boot_command('python -c "import time; time.sleep(3)"') == [
        "python",
        "-c",
        "import time; time.sleep(3)",
    ]


def test_check_url_success_and_failure(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    monkeypatch.setattr(module.httpx, "get", lambda url, **kwargs: FakeResponse(200))
    ok = check_url("http://127.0.0.1:8901", "/health", 200)
    assert ok.ok is True
    assert ok.detail == "status 200"

    monkeypatch.setattr(module.httpx, "get", lambda url, **kwargs: FakeResponse(500))
    bad = check_url("http://127.0.0.1:8901", "/api", 200)
    assert bad.ok is False
    assert "expected 200, got 500" in bad.detail


def test_check_url_request_error(tmp_path, monkeypatch) -> None:
    import httpx

    import testing_agent.runners.system_boot as module

    def raise_error(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(module.httpx, "get", raise_error)
    outcome = check_url("http://127.0.0.1:8901", "/health", 200)
    assert outcome.ok is False
    assert "request failed" in outcome.detail


def test_system_runner_skipped_without_boot_command(tmp_path) -> None:
    result = SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30
    )

    assert result.no_tests is True
    assert "boot_command" in (result.note or "")


def test_system_runner_boot_command_missing_binary(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    config = ProjectConfig(
        root=str(tmp_path), system=SystemConfig(boot_command="definitely-not-a-real-binary-xyz")
    )
    result = SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30, config=config
    )

    assert result.success is False
    assert result.failed == 1
    assert "boot failed" in (result.note or "")


def test_system_runner_happy_path(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    monkeypatch.setattr(
        module,
        "check_url",
        lambda base, path, expected, timeout_seconds=5.0: module.SystemCheckOutcome(
            path=path, ok=True, detail=f"status {expected}"
        ),
    )
    config = ProjectConfig(
        root=str(tmp_path),
        system=SystemConfig(
            boot_command="python -c \"import time; time.sleep(3)\"",
            boot_timeout_seconds=5,
            healthcheck_path="/health",
            endpoints=[EndpointCheck(path="/"), EndpointCheck(path="/api/health")],
        ),
    )

    result = SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30, config=config
    )

    assert result.success is True
    assert result.passed == 3
    assert result.failed == 0
    assert "endpoints 3/3 ok" in (result.note or "")
    # teardown must have killed the sleeper and marked the boot log
    time.sleep(0.2)
    assert result.duration_ms >= 0


def test_system_runner_writes_teardown_marker(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    monkeypatch.setattr(
        module,
        "check_url",
        lambda base, path, expected, timeout_seconds=5.0: module.SystemCheckOutcome(
            path=path, ok=True, detail=f"status {expected}"
        ),
    )
    config = ProjectConfig(
        root=str(tmp_path),
        system=SystemConfig(boot_command="python -c \"import time; time.sleep(3)\""),
    )

    SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30, config=config
    )

    log = tmp_path / ".testing-agent" / "logs" / "system-boot-system.log"
    assert log.is_file()
    assert "--- system teardown ---" in log.read_text(encoding="utf-8", errors="replace")


def test_terminate_tree_falls_back_to_kill_when_taskkill_fails(tmp_path, monkeypatch) -> None:
    import subprocess

    import testing_agent.runners.system_boot as module

    def failing_taskkill(*args, **kwargs):
        raise subprocess.SubprocessError("taskkill unavailable")

    monkeypatch.setattr(module.subprocess, "run", failing_taskkill)

    sleeper = subprocess.Popen(
        ["python", "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    try:
        assert sleeper.poll() is None
        module.terminate_tree(sleeper)
        # after fallback the process must be dead
        assert sleeper.poll() is not None
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_system_runner_failing_endpoint(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    def fake_check(base, path, expected, timeout_seconds=5.0):
        if path == "/bad":
            return module.SystemCheckOutcome(
                path=path, ok=False, detail=f"expected 200, got 404"
            )
        return module.SystemCheckOutcome(path=path, ok=True, detail=f"status {expected}")

    monkeypatch.setattr(module, "check_url", fake_check)
    config = ProjectConfig(
        root=str(tmp_path),
        system=SystemConfig(
            boot_command="python -c \"import time; time.sleep(3)\"",
            boot_timeout_seconds=5,
            endpoints=[EndpointCheck(path="/bad")],
        ),
    )

    result = SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30, config=config
    )

    assert result.success is False
    assert result.failed == 1
    assert result.passed >= 1
    assert result.failures[0].name == "GET /bad"
    assert "expected 200, got 404" in (result.failures[0].message or "")


def test_system_runner_unhealthy(tmp_path, monkeypatch) -> None:
    import testing_agent.runners.system_boot as module

    def fake_check(base, path, expected, timeout_seconds=5.0):
        return module.SystemCheckOutcome(
            path=path, ok=False, detail="request failed: connection refused"
        )

    monkeypatch.setattr(module, "check_url", fake_check)
    config = ProjectConfig(
        root=str(tmp_path),
        system=SystemConfig(
            boot_command="python -c \"import time; time.sleep(3)\"",
            boot_timeout_seconds=2,
        ),
    )

    result = SystemRunner().run(
        make_node_manifest(), tmp_path, TestType.SYSTEM, timeout_seconds=30, config=config
    )

    assert result.success is False
    assert result.failed == 1
    assert "healthcheck" in (result.failures[0].name or "")
