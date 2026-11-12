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


def build_report(target: str, results: list[RunResult], gate: GateSummary) -> dict[str, Any]:
    """Assemble the canonical report dict shared by all renderers."""
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": target,
        "verdict": "PASS" if gate.passed else "FAIL",
        "results": [result.model_dump(mode="json") for result in results],
        "gate": gate.model_dump(),
    }
