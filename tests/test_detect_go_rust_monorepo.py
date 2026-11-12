"""Tests for Go/Rust detection and monorepo behaviour."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.detect import detect_project
from testing_agent.detect.golang import detect_go, detect_rust
from testing_agent.detect.models import PackageManager, Stack


def test_detect_go(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.23\n", encoding="utf-8")
    manifest = detect_go(tmp_path)

    assert manifest is not None
    assert manifest.stack == Stack.GO
    assert manifest.name == "example.com/app"
    assert manifest.test_runner == "go"


def test_detect_rust(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "my-crate"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    manifest = detect_rust(tmp_path)

    assert manifest is not None
    assert manifest.stack == Stack.RUST
    assert manifest.name == "my-crate"
    assert manifest.test_runner == "cargo"


def test_empty_directory_yields_no_manifests(tmp_path: Path) -> None:
    result = detect_project(tmp_path)

    assert result.manifests == []
    assert result.is_monorepo is False


def test_single_root_project_is_not_monorepo(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "root"}), encoding="utf-8")
    result = detect_project(tmp_path)

    assert len(result.manifests) == 1
    assert result.is_monorepo is False


def test_monorepo_root_plus_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "root"}), encoding="utf-8")
    sub = tmp_path / "packages"
    sub.mkdir()
    (sub / "pyproject.toml").write_text('[project]\nname = "sub"\n', encoding="utf-8")
    result = detect_project(tmp_path)

    assert result.is_monorepo is True
    assert len(result.manifests) == 2
    directories = {m.directory for m in result.manifests}
    assert directories == {"", "packages"}
    stacks = {m.stack for m in result.manifests}
    assert stacks == {Stack.NODE, Stack.PYTHON}


def test_skipped_directories_are_not_scanned(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "root"}), encoding="utf-8")
    nested = tmp_path / "node_modules" / "somepkg"
    nested.mkdir(parents=True)
    (nested / "package.json").write_text(json.dumps({"name": "noise"}), encoding="utf-8")
    result = detect_project(tmp_path)

    assert result.is_monorepo is False
    assert [m.name for m in result.manifests] == ["root"]


def test_go_detected_by_detect_project(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text("module example.com/app\n", encoding="utf-8")
    result = detect_project(tmp_path)

    assert len(result.manifests) == 1
    assert result.manifests[0].stack == Stack.GO
