"""Gate policy engine: decide whether a run is allowed to pass."""

from __future__ import annotations

from pydantic import BaseModel

from testing_agent.config import GatePolicy
from testing_agent.runners.base import RunResult, TestType


class GateCheck(BaseModel):
    """One named check evaluated by the gate."""

    name: str
    passed: bool
    detail: str = ""


class GateResult(BaseModel):
    """Overall gate verdict plus its checks."""

    passed: bool
    checks: list[GateCheck] = []


def _results_for(results: list[RunResult], test_type: TestType) -> list[RunResult]:
    return [r for r in results if r.test_type == test_type]


def evaluate(
    results: list[RunResult],
    policy: GatePolicy,
    run_type: TestType,
) -> GateResult:
    """Evaluate the policy against the run results for `run_type`."""
    checks: list[GateCheck] = []
    required = policy.require_types or ["unit"]

    if run_type.value not in required:
        checks.append(
            GateCheck(
                name=f"{run_type.value}-type-not-required",
                passed=True,
                detail=f"'{run_type.value}' is not a required gate type; informational run",
            )
        )
        return GateResult(passed=True, checks=checks)

    typed = _results_for(results, run_type)
    if not typed:
        checks.append(
            GateCheck(
                name=f"{run_type.value}-runner-present",
                passed=not policy.fail_on_missing_runner,
                detail=f"no runner available for '{run_type.value}'",
            )
        )
        checks.append(
            GateCheck(
                name=f"{run_type.value}-tests-present",
                passed=not policy.fail_on_no_tests,
                detail="nothing ran",
            )
        )
        return GateResult(passed=all(c.passed for c in checks), checks=checks)

    for result in typed:
        scope = result.manifest_directory or "."
        if result.missing_runner:
            checks.append(
                GateCheck(
                    name=f"{run_type.value}-runner-present:{scope}",
                    passed=not policy.fail_on_missing_runner,
                    detail=f"runner executable not found ({result.runner})",
                )
            )
            continue
        if result.no_tests:
            checks.append(
                GateCheck(
                    name=f"{run_type.value}-tests-present:{scope}",
                    passed=not policy.fail_on_no_tests,
                    detail="no tests found",
                )
            )
            continue

        checks.append(
            GateCheck(
                name=f"{run_type.value}-suite-passed:{scope}",
                passed=result.success,
                detail=(
                    f"{result.passed} passed, {result.failed} failed, "
                    f"{result.errors} errors ({result.runner})"
                ),
            )
        )
        checks.append(
            GateCheck(
                name=f"{run_type.value}-pass-rate:{scope}",
                passed=result.pass_rate >= policy.min_pass_rate,
                detail=f"{result.pass_rate:.0%} >= {policy.min_pass_rate:.0%} required",
            )
        )

    return GateResult(passed=all(check.passed for check in checks), checks=checks)
