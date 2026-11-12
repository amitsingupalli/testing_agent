"""Detection of Python projects (pyproject.toml / requirements*.txt)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from testing_agent.detect.models import PackageManager, ProjectManifest, Stack

REQUIREMENT_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
    "requirements_dev.txt",
    "requirements-prod.txt",
)


def _iter_dependency_names(data: dict) -> list[str]:
    names: list[str] = []
    project = data.get("project") or {}
    for dep in project.get("dependencies") or []:
        names.append(str(dep))
    dependency_groups = data.get("dependency-groups") or {}
    for group in dependency_groups.values():
        if isinstance(group, list):
            names.extend(str(dep) for dep in group)
    poetry = (data.get("tool") or {}).get("poetry") or {}
    for section in ("dependencies", "dev-dependencies", "group"):
        section_data = poetry.get(section)
        if isinstance(section_data, dict):
            names.extend(section_data.keys())
    return names


def _infer_package_manager(directory: Path) -> PackageManager:
    if (directory / "uv.lock").is_file():
        return PackageManager.UV
    if (directory / "poetry.lock").is_file():
        return PackageManager.PIP
    if any((directory / name).is_file() for name in REQUIREMENT_FILES):
        return PackageManager.PIP
    return PackageManager.UV  # reasonable default for modern Python projects


def detect_python(directory: Path) -> ProjectManifest | None:
    """Return a manifest when the directory is a Python project."""
    pyproject = directory / "pyproject.toml"
    has_requirements = any((directory / name).is_file() for name in REQUIREMENT_FILES)
    if not pyproject.is_file() and not has_requirements:
        return None

    data: dict = {}
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            data = {}

    project_name = (data.get("project") or {}).get("name")
    deps = [name.lower() for name in _iter_dependency_names(data)]
    has_pytest = any(dep.split(">=")[0].split("==")[0].strip() == "pytest" for dep in deps)

    return ProjectManifest(
        directory="",
        stack=Stack.PYTHON,
        package_manager=_infer_package_manager(directory),
        name=project_name,
        test_runner="pytest" if (has_pytest or has_requirements) else "pytest",
    )
