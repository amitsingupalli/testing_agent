"""Stack detection for testing-agent."""

from __future__ import annotations

from pathlib import Path

from testing_agent.detect.models import DetectionResult, ProjectManifest
from testing_agent.detect.node import detect_node
from testing_agent.detect.python import detect_python

SKIP_DIRECTORY_NAMES = {
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    "__pycache__",
    ".git",
    ".hg",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
}


def _subdirectories(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        child
        for child in root.iterdir()
        if child.is_dir() and not child.name.startswith(".") and child.name not in SKIP_DIRECTORY_NAMES
    )


def _detect_directory(directory: Path, relative: str) -> ProjectManifest | None:
    manifest = detect_node(directory)
    if manifest is not None:
        manifest.directory = relative
        return manifest
    manifest = detect_python(directory)
    if manifest is not None:
        manifest.directory = relative
        return manifest
    return None


def detect_project(root: Path) -> DetectionResult:
    """Detect every project manifest at the root and one level deep."""
    root = root.resolve()
    manifests: list[ProjectManifest] = []

    root_manifest = _detect_directory(root, "")
    if root_manifest is not None:
        manifests.append(root_manifest)

    for subdir in _subdirectories(root):
        manifest = _detect_directory(subdir, subdir.name)
        if manifest is not None:
            manifests.append(manifest)

    return DetectionResult(
        root=str(root),
        manifests=manifests,
        is_monorepo=len(manifests) > 1,
    )
