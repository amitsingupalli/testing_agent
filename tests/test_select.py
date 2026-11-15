"""Tests for diff-aware test selection."""

from __future__ import annotations

from pathlib import Path

from testing_agent.select import (
    Selection,
    candidate_test_paths,
    is_full_run_trigger,
    is_test_file,
    select_tests,
)


def test_is_test_file_patterns() -> None:
    assert is_test_file("tests/unit/math.test.js")
    assert is_test_file("tests/test_math.py")
    assert is_test_file("src/app.spec.ts")
    assert is_test_file("src/__tests__/foo.jsx.test.js") or is_test_file("src/__tests__/foo.js")
    assert not is_test_file("src/math.js")
    assert not is_test_file("app.py")


def test_is_full_run_trigger() -> None:
    assert is_full_run_trigger("package.json")
    assert is_full_run_trigger("src/package.json") or is_full_run_trigger("web/package.json")
    assert is_full_run_trigger("pyproject.toml")
    assert is_full_run_trigger("requirements.txt")
    assert is_full_run_trigger("requirements-dev.txt")
    assert not is_full_run_trigger("src/math.js")
    assert not is_full_run_trigger("tests/test_x.py")


def test_candidates_node_mirror() -> None:
    candidates = candidate_test_paths("src/math.js")

    assert "tests/unit/math.test.js" in candidates
    assert "tests/math.test.js" in candidates
    assert "src/__tests__/math.test.js" in candidates


def test_candidates_node_spec() -> None:
    candidates = candidate_test_paths("src/app.ts")

    assert "tests/unit/app.spec.ts" in candidates
    assert "src/__tests__/app.spec.ts" in candidates


def test_candidates_python() -> None:
    candidates = candidate_test_paths("src/utils/str.py")

    assert "tests/test_str.py" in candidates
    assert "tests/unit/test_str.py" in candidates
    assert "tests/unit/utils/test_str.py" in candidates
    assert "src/utils/test_str.py" in candidates


def test_candidates_test_file_itself() -> None:
    assert candidate_test_paths("tests/unit/math.test.js") == ["tests/unit/math.test.js"]
    assert candidate_test_paths("tests/test_math.py") == ["tests/test_math.py"]


def test_select_tests_no_changes_runs_all() -> None:
    selection = select_tests([])

    assert selection.mode == "all"
    assert "no changed files" in selection.reason


def test_select_tests_config_change_runs_all() -> None:
    selection = select_tests(["src/math.js", "package.json"])

    assert selection.mode == "all"
    assert "package.json" in selection.reason


def test_select_tests_affected_with_fs_check(tmp_path: Path) -> None:
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "math.test.js").write_text("test")

    selection = select_tests(["src/math.js", "src/other.js"], root=tmp_path)

    assert selection.mode == "affected"
    assert selection.test_files == ["tests/unit/math.test.js"]


def test_select_tests_none_when_no_mapping(tmp_path: Path) -> None:
    selection = select_tests(["src/unknown.js"], root=tmp_path)

    assert selection.mode == "none"


def test_select_tests_monorepo_scoping(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "tests" / "unit").mkdir(parents=True)
    (web / "tests" / "unit" / "app.test.js").write_text("test")

    selection = select_tests(["web/src/app.js"], manifest_directory="web", root=tmp_path)

    assert selection.mode == "affected"
    assert selection.test_files == ["tests/unit/app.test.js"]

    # change outside the manifest is ignored
    outside = select_tests(["other/src/app.js"], manifest_directory="web", root=tmp_path)
    assert outside.mode == "none"


def test_select_tests_without_fs_check_returns_candidates() -> None:
    selection = select_tests(["src/math.js"], check_exists=False)

    assert selection.mode == "affected"
    assert "tests/unit/math.test.js" in selection.test_files


def test_selection_defaults() -> None:
    empty = Selection(mode="all")
    assert empty.changed_files == []
    assert empty.test_files == []
