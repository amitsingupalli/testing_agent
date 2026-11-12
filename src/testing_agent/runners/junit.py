"""Parser for JUnit XML results.

Works with pytest (--junit-xml), vitest (--reporter=junit), and the
built-in `node --test --test-reporter junit` reporter.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, Field

from testing_agent.runners.base import FailureInfo

_MESSAGE_PREVIEW_CHARS = 500


class JunitSummary(BaseModel):
    """Counts and failures extracted from a JUnit XML file."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[FailureInfo] = Field(default_factory=list)


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text.strip()
    if len(cleaned) > _MESSAGE_PREVIEW_CHARS:
        cleaned = cleaned[:_MESSAGE_PREVIEW_CHARS] + "..."
    return cleaned or None


def parse_junit(xml_path: Path) -> JunitSummary:
    """Parse a JUnit XML file into counts and failure details."""
    summary = JunitSummary()
    try:
        tree = ET.parse(xml_path)
    except (OSError, ET.ParseError):
        return summary

    for testcase in tree.getroot().iter("testcase"):
        name = testcase.get("name") or "<unnamed>"
        classname = testcase.get("classname")
        display_name = f"{classname}::{name}" if classname else name

        children = list(testcase)
        if any(child.tag == "failure" for child in children):
            summary.failed += 1
            message = next(
                (child.get("message") for child in children if child.tag == "failure"), None
            )
            body = next(
                (child.text for child in children if child.tag == "failure"), None
            )
            summary.failures.append(
                FailureInfo(name=display_name, message=_clean(message or body))
            )
        elif any(child.tag == "error" for child in children):
            summary.errors += 1
            message = next(
                (child.get("message") for child in children if child.tag == "error"), None
            )
            summary.failures.append(FailureInfo(name=display_name, message=_clean(message)))
        elif any(child.tag == "skipped" for child in children):
            summary.skipped += 1
        else:
            summary.passed += 1

    return summary
