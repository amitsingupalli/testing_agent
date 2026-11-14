"""Test runner adapters for every supported stack."""

from __future__ import annotations

from pathlib import Path

from testing_agent.config import ProjectConfig
from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import Runner, TestType
from testing_agent.runners.jest_unit import JestRunner
from testing_agent.runners.node_unit import NodeTestRunner
from testing_agent.runners.perf_autocannon import AutocannonRunner
from testing_agent.runners.perf_k6 import K6Runner
from testing_agent.runners.perf_lighthouse import LighthouseRunner
from testing_agent.runners.pytest_unit import PytestRunner
from testing_agent.runners.security_bandit import BanditRunner
from testing_agent.runners.security_npm import NpmAuditRunner
from testing_agent.runners.security_pip import PipAuditRunner
from testing_agent.runners.security_semgrep import SemgrepRunner
from testing_agent.runners.system_boot import SystemRunner
from testing_agent.runners.vitest_unit import VitestRunner

_UNIT_ADAPTERS: list[Runner] = [PytestRunner(), VitestRunner(), JestRunner(), NodeTestRunner()]

_TYPE_RUNNERS: dict[TestType, list[Runner]] = {
    TestType.SECURITY: [
        NpmAuditRunner(),
        PipAuditRunner(),
        BanditRunner(),
        SemgrepRunner(),
    ],
    TestType.PERFORMANCE: [
        AutocannonRunner(),
        K6Runner(),
        LighthouseRunner(),
    ],
    TestType.SYSTEM: [
        SystemRunner(),
    ],
}


def select_runner(manifest: ProjectManifest, test_type: TestType) -> Runner | None:
    """Pick the adapter that can execute `test_type` for this manifest.

    Unit, integration, and regression all use the same adapters today:
    integration is directory-scoped inside each adapter, and regression
    is a baseline re-run of the unit suite (diff-aware baselines land in
    Phase 2).
    """
    for adapter in _UNIT_ADAPTERS:
        if adapter.applies(manifest):
            return adapter
    return None


def select_type_runners(
    manifest: ProjectManifest,
    root: Path,
    test_type: TestType,
    config: ProjectConfig,
) -> list[Runner]:
    """All applicable runners for a test type (security/performance/system).

    Runners self-gate at run time (config opt-ins, tool availability) and
    emit no_tests results when skipped; the gate ignores those results, so
    callers may simply run every returned runner.
    """
    candidates = _TYPE_RUNNERS.get(test_type, [])
    return [runner for runner in candidates if runner.applies(manifest)]


def registered_adapters() -> list[Runner]:
    """All registered adapters (for diagnostics)."""
    return list(_UNIT_ADAPTERS)


def registered_type_runners() -> dict[str, list[str]]:
    """Map of test type -> registered runner ids (for diagnostics)."""
    return {test_type.value: [r.id for r in runners] for test_type, runners in _TYPE_RUNNERS.items()}
