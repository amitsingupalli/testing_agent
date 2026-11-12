"""Tests for Python stack detection."""

from __future__ import annotations

from pathlib import Path

from testing_agent.detect.models import PackageManager, Stack
from testing_agent.detect.python import detect_python


def test_detect_python_missing_files(tmp_path: Path) -> None:
    assert detect_python(tmp_path) is None


def test_detect_python_pyproject_with_uv(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "myproj"\ndependencies = ["typer>=0.12"]\n'
        "[dependency-groups]\ndev = [\"pytest>=8.2\"]\n",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").touch()
    manifest = detect_python(tmp_path)

    assert manifest is not None
    assert manifest.stack == Stack.PYTHON
    assert manifest.name == "myproj"
    assert manifest.test_runner == "pytest"
    assert manifest.package_manager == PackageManager.UV


def test_detect_python_requirements_only(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("flask>=3.0\npytest>=8.2\n", encoding="utf-8")
    manifest = detect_python(tmp_path)

    assert manifest is not None
    assert manifest.stack == Stack.PYTHON
    assert manifest.test_runner == "pytest"
    assert manifest.package_manager == PackageManager.PIP
    assert manifest.name is None


def test_detect_python_poetry_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[tool.poetry.dependencies]\npython = "^3.14"\npytest = "^8.0"\n',
        encoding="utf-8",
    )
    (tmp_path / "poetry.lock").touch()
    manifest = detect_python(tmp_path)

    assert manifest is not None
    assert manifest.package_manager == PackageManager.PIP
