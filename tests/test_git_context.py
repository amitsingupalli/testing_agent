"""Tests for the git context collector (parser + integration)."""

from __future__ import annotations

from pathlib import Path

from testing_agent.git_context import GitContext, _is_test_path, _parse_porcelain, collect_git_context


def test_parse_porcelain_basic() -> None:
    text = " M src/app.py\n?? new_file.py\nA  added.py\n"
    assert _parse_porcelain(text) == ["src/app.py", "new_file.py", "added.py"]


def test_parse_porcelain_rename_takes_new_path() -> None:
    text = "R  old.py -> new.py\n"
    assert _parse_porcelain(text) == ["new.py"]


def test_parse_porcelain_quoted_paths() -> None:
    text = ' M "weird name.py"\n'
    assert _parse_porcelain(text) == ["weird name.py"]


def test_is_test_path_detection() -> None:
    assert _is_test_path("tests/unit/test_app.py")
    assert _is_test_path("src/app.test.js")
    assert _is_test_path("tests/thing.spec.ts")
    assert not _is_test_path("src/app.py")
    assert not _is_test_path("src/contest.py")  # 'tests' must be a directory part


def test_collect_git_context_on_real_repo(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "app.py"], cwd=tmp_path, check=True, capture_output=True)

    context = collect_git_context(tmp_path)

    assert context.is_repo is True
    assert "app.py" in context.changed_files
    assert context.has_source_changes is True
    assert context.has_test_changes is False


def test_collect_git_context_outside_repo(tmp_path: Path) -> None:
    context = collect_git_context(tmp_path)

    assert context.is_repo is False
    assert context.changed_files == []
    assert context.summary() == "not a git repository"


def test_git_context_defaults() -> None:
    context = GitContext()
    assert context.is_repo is False
    assert context.summary() == "not a git repository"
