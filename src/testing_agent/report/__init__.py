"""Report assembly and rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from testing_agent.runners.base import RunResult


class GateSummary(BaseModel):
    """Gate verdict included in reports."""

    passed: bool = True
    checks: list[dict[str, Any]] = []


def _combined_summary(result_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate totals across all runners, grouped by test type."""
    by_type: dict[str, dict[str, Any]] = {}
    total = {"runners": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for result in result_dicts:
        test_type = str(result.get("test_type", "unknown"))
        bucket = by_type.setdefault(
            test_type,
            {"runners": [], "passed": 0, "failed": 0, "errors": 0, "skipped": 0},
        )
        count = not (result.get("no_tests") or result.get("missing_runner"))
        if count:
            runner = str(result.get("runner", "?"))
            if runner not in bucket["runners"]:
                bucket["runners"].append(runner)
            total["runners"] += 1
            for key in ("passed", "failed", "errors", "skipped"):
                bucket[key] += int(result.get(key, 0) or 0)
                total[key] += int(result.get(key, 0) or 0)
    return {
        "total": total,
        "by_type": by_type,
        "active": bool(result_dicts) and any(
            not (r.get("no_tests") or r.get("missing_runner")) for r in result_dicts
        ),
    }


def build_report(
    target: str,
    results: list[RunResult],
    gate: GateSummary,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the canonical report dict shared by all renderers.

    `extra` merges additional top-level sections (e.g. regression context).
    """
    result_dicts: list[dict[str, Any]] = []
    for result in results:
        dumped = result.model_dump(mode="json")
        dumped["verdict"] = result.verdict  # property, not a field — inject manually
        result_dicts.append(dumped)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": target,
        "verdict": "PASS" if gate.passed else "FAIL",
        "results": result_dicts,
        "summary": _combined_summary(result_dicts),
        "gate": gate.model_dump(),
    }
    if extra:
        report.update(extra)
    return report
