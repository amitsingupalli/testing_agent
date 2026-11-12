"""Tests for Node.js stack detection."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.detect.models import PackageManager, Stack
from testing_agent.detect.node import detect_node


def write_package_json(directory: Path, **kwargs) -> None:
    (directory / "package.json").write_text(json.dumps(kwargs), encoding="utf-8")


def test_detect_node_missing_package_json(tmp_path: Path) -> None:
    assert detect_node(tmp_path) is None


def test_detect_node_minimal_defaults_to_builtin_runner(tmp_path: Path) -> None:
    write_package_json(tmp_path, name="demo", version="1.0.0")
    manifest = detect_node(tmp_path)

    assert manifest is not None
    assert manifest.stack == Stack.NODE
    assert manifest.name == "demo"
    assert manifest.test_runner == "node"
    assert manifest.package_manager == PackageManager.NPM


def test_detect_node_detects_vitest(tmp_path: Path) -> None:
    write_package_json(
        tmp_path,
        name="demo",
        devDependencies={"vitest": "^3.0.0"},
    )
    manifest = detect_node(tmp_path)

    assert manifest is not None
    assert manifest.test_runner == "vitest"


def test_detect_node_detects_jest(tmp_path: Path) -> None:
    write_package_json(
        tmp_path,
        name="demo",
        devDependencies={"jest": "^29.0.0"},
    )
    manifest = detect_node(tmp_path)

    assert manifest is not None
    assert manifest.test_runner == "jest"


def test_detect_node_node_test_script(tmp_path: Path) -> None:
    write_package_json(
        tmp_path,
        name="demo",
        scripts={"test": "node --test tests/"},
    )
    manifest = detect_node(tmp_path)

    assert manifest is not None
    assert manifest.test_runner == "node"


def test_detect_node_package_managers_from_lockfiles(tmp_path: Path) -> None:
    write_package_json(tmp_path, name="demo")
    (tmp_path / "pnpm-lock.yaml").touch()
    manifest = detect_node(tmp_path)

    assert manifest is not None
    assert manifest.package_manager == PackageManager.PNPM


def test_detect_node_invalid_json_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{ not json", encoding="utf-8")
    assert detect_node(tmp_path) is None
