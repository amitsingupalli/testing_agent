"""Tests for the test-type runner registry."""

from __future__ import annotations

from pathlib import Path

from testing_agent.config import ProjectConfig
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners import registered_type_runners, select_type_runners
from testing_agent.runners.base import TestType
from testing_agent.runners.perf_autocannon import AutocannonRunner
from testing_agent.runners.perf_k6 import K6Runner
from testing_agent.runners.perf_lighthouse import LighthouseRunner
from testing_agent.runners.security_bandit import BanditRunner
from testing_agent.runners.security_npm import NpmAuditRunner
from testing_agent.runners.security_pip import PipAuditRunner
from testing_agent.runners.security_semgrep import SemgrepRunner
from testing_agent.runners.system_boot import SystemRunner


def node_manifest() -> ProjectManifest:
    return ProjectManifest(stack=Stack.NODE, test_runner="node")


def python_manifest() -> ProjectManifest:
    return ProjectManifest(stack=Stack.PYTHON, test_runner="pytest")


def test_registered_type_runners_map() -> None:
    registered = registered_type_runners()

    assert registered["security"] == ["npm-audit", "pip-audit", "bandit", "semgrep"]
    assert registered["performance"] == ["autocannon", "k6", "lighthouse"]
    assert registered["system"] == ["system-boot"]


def test_select_security_runners_node(tmp_path) -> None:
    runners = select_type_runners(
        node_manifest(), tmp_path, TestType.SECURITY, ProjectConfig(root=str(tmp_path))
    )

    ids = [r.id for r in runners]
    assert NpmAuditRunner().id in ids
    assert SemgrepRunner().id in ids
    assert PipAuditRunner().id not in ids
    assert BanditRunner().id not in ids


def test_select_security_runners_python(tmp_path) -> None:
    runners = select_type_runners(
        python_manifest(), tmp_path, TestType.SECURITY, ProjectConfig(root=str(tmp_path))
    )

    ids = [r.id for r in runners]
    assert PipAuditRunner().id in ids
    assert BanditRunner().id in ids
    assert NpmAuditRunner().id not in ids
    assert SemgrepRunner().id in ids


def test_select_performance_runners_node(tmp_path) -> None:
    runners = select_type_runners(
        node_manifest(), tmp_path, TestType.PERFORMANCE, ProjectConfig(root=str(tmp_path))
    )

    ids = [r.id for r in runners]
    assert AutocannonRunner().id in ids
    assert K6Runner().id in ids
    assert LighthouseRunner().id in ids


def test_select_performance_runners_python_empty(tmp_path) -> None:
    runners = select_type_runners(
        python_manifest(), tmp_path, TestType.PERFORMANCE, ProjectConfig(root=str(tmp_path))
    )

    assert runners == []


def test_select_system_runners(tmp_path) -> None:
    node_runners = select_type_runners(
        node_manifest(), tmp_path, TestType.SYSTEM, ProjectConfig(root=str(tmp_path))
    )
    python_runners = select_type_runners(
        python_manifest(), tmp_path, TestType.SYSTEM, ProjectConfig(root=str(tmp_path))
    )

    assert [r.id for r in node_runners] == ["system-boot"]
    assert [r.id for r in python_runners] == ["system-boot"]
    assert isinstance(node_runners[0], SystemRunner)


def test_select_type_runners_ignores_unit_types(tmp_path) -> None:
    runners = select_type_runners(
        node_manifest(), tmp_path, TestType.UNIT, ProjectConfig(root=str(tmp_path))
    )

    assert runners == []
