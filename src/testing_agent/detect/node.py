"""Detection of Node.js projects (package.json)."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.detect.models import PackageManager, ProjectManifest, Stack


def _infer_package_manager(directory: Path) -> PackageManager:
    if (directory / "pnpm-lock.yaml").is_file():
        return PackageManager.PNPM
    if (directory / "yarn.lock").is_file():
        return PackageManager.YARN
    if (directory / "package-lock.json").is_file():
        return PackageManager.NPM
    return PackageManager.NPM


def _infer_test_runner(data: dict, deps: dict[str, str]) -> str:
    if "vitest" in deps:
        return "vitest"
    if "jest" in deps:
        return "jest"
    scripts = data.get("scripts") or {}
    test_script = scripts.get("test") or ""
    if "node --test" in test_script:
        return "node"
    return "node"  # built-in runner is the safe default for Node projects


def detect_node(directory: Path) -> ProjectManifest | None:
    """Return a manifest when the directory contains a package.json."""
    package_file = directory / "package.json"
    if not package_file.is_file():
        return None
    try:
        data = json.loads(package_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None

    deps: dict[str, str] = {}
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        section_deps = data.get(section)
        if isinstance(section_deps, dict):
            deps.update(section_deps)

    return ProjectManifest(
        directory="",
        stack=Stack.NODE,
        package_manager=_infer_package_manager(directory),
        name=data.get("name"),
        test_runner=_infer_test_runner(data, deps),
    )
