"""Tests for the Python AST gap scanner."""

from __future__ import annotations

from pathlib import Path

from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.generate.gap import scan_gaps, scan_python_gaps


def make_manifest() -> ProjectManifest:
    return ProjectManifest(directory="", stack=Stack.PYTHON, test_runner="pytest")


def build_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[dependency-groups]\ndev = ["pytest>=8"]\n', encoding="utf-8"
    )
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef _private():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "shapes.py").write_text(
        "class Circle:\n    pass\n",
        encoding="utf-8",
    )


def test_scan_python_gaps(tmp_path: Path) -> None:
    build_project(tmp_path)
    gaps = scan_gaps(tmp_path, make_manifest())

    files = {g.file for g in gaps}
    assert files == {"calc.py", "shapes.py"}
    calc = next(g for g in gaps if g.file == "calc.py")
    assert calc.untested == ["add"]
    assert calc.tested == []


def test_private_functions_are_ignored(tmp_path: Path) -> None:
    build_project(tmp_path)
    gaps = scan_python_gaps(tmp_path)
    names = [name for g in gaps for name in g.untested]
    assert "_private" not in names


def test_referenced_symbols_marked_tested(tmp_path: Path) -> None:
    build_project(tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "import calc\n\ndef test_add():\n    assert calc.add(1, 2) == 3\n",
        encoding="utf-8",
    )
    gaps = scan_python_gaps(tmp_path)

    calc = next((g for g in gaps if g.file == "calc.py"), None)
    assert calc is None  # fully covered now
    shapes = next(g for g in gaps if g.file == "shapes.py")
    assert shapes.untested == ["Circle"]


def test_syntax_error_file_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    assert scan_python_gaps(tmp_path) == []


def test_test_directories_are_not_scanned(tmp_path: Path) -> None:
    build_project(tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "helper.py").write_text("def helper_tested_only():\n    return 1\n", encoding="utf-8")
    gaps = scan_python_gaps(tmp_path)
    files = {g.file for g in gaps}
    assert "tests/helper.py" not in files
