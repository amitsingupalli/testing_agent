"""Tests for the gate policy engine."""

from __future__ import annotations

from testing_agent.config import GatePolicy
from testing_agent.gate import evaluate
from testing_agent.runners.base import RunResult, TestType


def make_result(**kwargs) -> RunResult:
    defaults = {"runner": "node", "test_type": TestType.UNIT}
    defaults.update(kwargs)
    return RunResult(**defaults)


def test_passing_result_gates_pass() -> None:
    result = make_result(passed=4, success=True, exit_code=0)
    gate = evaluate([result], GatePolicy(), TestType.UNIT)

    assert gate.passed is True


def test_failing_result_gates_fail() -> None:
    result = make_result(passed=2, failed=2, success=False, exit_code=1)
    gate = evaluate([result], GatePolicy(), TestType.UNIT)

    assert gate.passed is False
    names = [c.name for c in gate.checks]
    assert any("suite-passed" in name for name in names)


def test_min_pass_rate_boundary() -> None:
    policy = GatePolicy(min_pass_rate=0.9)
    result = make_result(passed=9, failed=1, success=False, exit_code=1)
    gate = evaluate([result], policy, TestType.UNIT)

    rate_checks = [c for c in gate.checks if "pass-rate" in c.name]
    assert rate_checks[0].passed is True  # 90% meets the 90% requirement


def test_no_runner_available_defaults_to_warn() -> None:
    gate = evaluate([], GatePolicy(), TestType.UNIT)

    assert gate.passed is True  # fail_on_missing_runner defaults to False


def test_no_runner_strict_policy_fails() -> None:
    policy = GatePolicy(fail_on_missing_runner=True, fail_on_no_tests=True)
    gate = evaluate([], policy, TestType.UNIT)

    assert gate.passed is False


def test_no_tests_defaults_to_warn() -> None:
    result = make_result(no_tests=True)
    gate = evaluate([result], GatePolicy(), TestType.UNIT)

    assert gate.passed is True


def test_missing_runner_result_respects_policy() -> None:
    policy = GatePolicy(fail_on_missing_runner=True)
    result = make_result(missing_runner=True)
    gate = evaluate([result], policy, TestType.UNIT)

    assert gate.passed is False


def test_non_required_type_is_informational() -> None:
    policy = GatePolicy(require_types=["unit"])
    result = make_result(passed=0, failed=5, success=False)
    gate = evaluate([result], policy, TestType.INTEGRATION)

    assert gate.passed is True
    assert gate.checks[0].name == "integration-type-not-required"


def test_regression_type_required_when_configured() -> None:
    policy = GatePolicy(require_types=["unit", "regression"])
    result = make_result(test_type=TestType.REGRESSION, passed=3, success=True)
    gate = evaluate([result], policy, TestType.REGRESSION)

    assert gate.passed is True
