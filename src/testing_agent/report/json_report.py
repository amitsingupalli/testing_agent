"""JSON report writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def report_dir(root: Path) -> Path:
    """Directory where reports are stored."""
    return root / ".testing-agent"


def write_json_report(root: Path, report: dict[str, Any]) -> Path:
    """Write last-report.json and return its path."""
    directory = report_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "last-report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def load_json_report(root: Path) -> dict[str, Any] | None:
    """Load the last report, or None when missing/invalid."""
    path = report_dir(root) / "last-report.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None
