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
        "gate": gate.model_dump(),
    }
    if extra:
        report.update(extra)
    return report
