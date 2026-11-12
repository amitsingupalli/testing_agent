"""Test runner adapters for every supported stack."""

from __future__ import annotations

from testing_agent.detect.models import ProjectManifest
from testing_agent.runners.base import Runner, TestType
from testing_agent.runners.jest_unit import JestRunner
from testing_agent.runners.node_unit import NodeTestRunner
from testing_agent.runners.pytest_unit import PytestRunner
from testing_agent.runners.vitest_unit import VitestRunner

_UNIT_ADAPTERS: list[Runner] = [PytestRunner(), VitestRunner(), JestRunner(), NodeTestRunner()]


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


def registered_adapters() -> list[Runner]:
    """All registered adapters (for diagnostics)."""
    return list(_UNIT_ADAPTERS)
