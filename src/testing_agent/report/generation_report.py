"""Markdown renderer for generation reports."""

from __future__ import annotations

from pathlib import Path

from testing_agent.generate.models import GenerationReport


def render_generation_markdown(report: GenerationReport) -> str:
    lines: list[str] = ["# testing-agent generation report", ""]
    lines.append(f"- **Backend:** {report.backend}")
    lines.append(f"- **Gap manifest:** {report.manifest_path or '_not written (LLM backend used)_'}")
    lines.append("")

    lines.append("| Source file | Test file | Rounds | Status | Note |")
    lines.append("| --- | --- | ---: | --- | --- |")
    for outcome in report.outcomes:
        status = "✅ PASS" if outcome.success else "❌ FAIL"
        note = outcome.note or outcome.error or ""
        lines.append(
            f"| `{outcome.source_file}` "
            f"| `{outcome.test_file or '—'}` "
            f"| {outcome.rounds} "
            f"| {status} "
            f"| {note[:120]} |"
        )
    lines.append("")

    failures = [outcome for outcome in report.outcomes if not outcome.success]
    if failures:
        lines.append("## Outcomes needing attention")
        lines.append("")
        for outcome in failures:
            lines.append(f"### `{outcome.source_file}`")
            lines.append("")
            lines.append(f"- backend: `{outcome.backend}`")
            if outcome.error:
                lines.append(f"- error: {outcome.error}")
            if outcome.note:
                lines.append(f"- note: {outcome.note}")
            lines.append("")

    return "\n".join(lines)


def write_generation_markdown(root: Path, report: GenerationReport) -> Path:
    """Write last-generation.md and return its path."""
    directory = Path(root) / ".testing-agent"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "last-generation.md"
    path.write_text(render_generation_markdown(report), encoding="utf-8")
    return path
