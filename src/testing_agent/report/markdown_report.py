"""Markdown report renderer."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    """Render a report dict as a GitHub-flavored markdown document."""
    lines: list[str] = []
    verdict = report.get("verdict", "UNKNOWN")
    verdict_badge = "✅ PASS" if verdict == "PASS" else "❌ FAIL"

    lines.append(f"# testing-agent report — {verdict_badge}")
    lines.append("")
    lines.append(f"- **Target:** `{report.get('target', '?')}`")
    lines.append(f"- **Generated:** {report.get('generated_at', '?')}")
    lines.append("")

    results = report.get("results") or []
    if results:
        lines.append("| Runner | Type | Project | Passed | Failed | Errors | Skipped | Time | Status |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
        for result in results:
            manifest = result.get("manifest_directory") or "."
            lines.append(
                f"| {result.get('runner', '?')} "
                f"| {result.get('test_type', '?')} "
                f"| `{manifest}` "
                f"| {result.get('passed', 0)} "
                f"| {result.get('failed', 0)} "
                f"| {result.get('errors', 0)} "
                f"| {result.get('skipped', 0)} "
                f"| {result.get('duration_ms', 0)} ms "
                f"| {result.get('verdict', result.get('runner', '?'))} |"
            )
        lines.append("")

        failure_rows: list[str] = []
        for result in results:
            for failure in result.get("failures") or []:
                failure_rows.append(
                    f"### `{result.get('runner')}` — {failure.get('name', '?')}\n\n"
                    "```\n"
                    f"{failure.get('message') or 'no message'}\n"
                    "```\n"
                )
        if failure_rows:
            lines.append("## Failures")
            lines.append("")
            lines.extend(failure_rows)
    else:
        lines.append("_No test runners ran for this target._")
        lines.append("")

    gate = report.get("gate") or {}
    lines.append("## Gate")
    lines.append("")
    lines.append(f"- **Verdict:** {verdict_badge}")
    for check in gate.get("checks") or []:
        mark = "✅" if check.get("passed") else "❌"
        lines.append(f"- {mark} **{check.get('name', '?')}** — {check.get('detail', '')}")
    lines.append("")

    regression = report.get("regression_context")
    if regression:
        lines.append("## Regression context")
        lines.append("")
        changed = regression.get("changed_files") or []
        lines.append(f"- Repository: {'yes' if regression.get('is_repo') else 'no'}")
        lines.append(f"- Changed files: {len(changed)}")
        for path in changed[:20]:
            lines.append(f"  - `{path}`")
        lines.append(
            f"- Test changes: {'yes' if regression.get('has_test_changes') else 'no'} · "
            f"Mode: {regression.get('mode', 'baseline')}"
        )
        lines.append("")

    return "\n".join(lines)


def write_markdown_report(root: Path, report: dict[str, Any]) -> Path:
    """Write last-report.md and return its path."""
    directory = Path(root) / ".testing-agent"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "last-report.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    return path
