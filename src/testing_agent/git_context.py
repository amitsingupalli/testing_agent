"""Git context for regression runs: which files changed since HEAD."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field


class GitContext(BaseModel):
    """Changed-file summary used to annotate regression baselines."""

    is_repo: bool = False
    changed_files: list[str] = Field(default_factory=list)
    has_test_changes: bool = False
    has_source_changes: bool = False

    def summary(self) -> str:
        if not self.is_repo:
            return "not a git repository"
        if not self.changed_files:
            return "working tree clean"
        return f"{len(self.changed_files)} changed file(s)"


def _parse_porcelain(text: str) -> list[str]:
    """Parse `git status --porcelain` output into changed paths."""
    paths: list[str] = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry.startswith('"') and entry.endswith('"'):
            entry = entry[1:-1]
        if entry:
            paths.append(entry.replace("\\", "/"))
    return paths


def _is_test_path(path: str) -> bool:
    name = Path(path).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name or name.startswith("test-"):
        return True
    parts = path.split("/")
    return any(part in ("tests", "test", "__tests__") for part in parts[:-1])


def collect_git_context(root: Path) -> GitContext:
    """Collect changed files relative to HEAD for the project root."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return GitContext()

    if completed.returncode != 0:
        return GitContext()

    changed = _parse_porcelain(completed.stdout)
    return GitContext(
        is_repo=True,
        changed_files=changed,
        has_test_changes=any(_is_test_path(path) for path in changed),
        has_source_changes=any(not _is_test_path(path) for path in changed),
    )
