"""Gap manifest writer: persist the scan result for agents to consume."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.generate.models import GapManifest


def _render_markdown(manifest: GapManifest) -> str:
    lines: list[str] = ["# testing-agent gap manifest", ""]
    lines.append(f"Root: `{manifest.root}` · Gaps: **{manifest.gap_count}**")
    lines.append("")
    lines.append("Generate tests for these symbols (public behavior only):")
    lines.append("")
    for file_gaps in manifest.files:
        lines.append(f"## `{file_gaps.file}`")
        lines.append("")
        for name in file_gaps.untested:
            symbol = next((s for s in file_gaps.symbols if s.name == name), None)
            kind = symbol.kind if symbol else "symbol"
            line = symbol.line if symbol else 0
            lines.append(f"- [ ] `{name}` ({kind}, line {line})")
        if file_gaps.tested:
            lines.append("")
            lines.append(f"_Already tested: {', '.join(f'`{n}`' for n in file_gaps.tested)}_")
        lines.append("")
    return "\n".join(lines)


def write_gap_manifest(root: Path, manifest: GapManifest) -> tuple[Path, Path]:
    """Write gap-manifest.md and gap-manifest.json; return (markdown, json) paths."""
    directory = Path(root) / ".testing-agent"
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = directory / "gap-manifest.md"
    json_path = directory / "gap-manifest.json"
    markdown_path.write_text(_render_markdown(manifest), encoding="utf-8")
    json_path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
    return markdown_path, json_path
