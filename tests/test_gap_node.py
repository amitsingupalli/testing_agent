"""Tests for the Node.js export gap scanner."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.generate.gap import scan_gaps, scan_node_gaps


def make_manifest() -> ProjectManifest:
    return ProjectManifest(directory="", stack=Stack.NODE, test_runner="node")


def test_scan_node_gaps_exports(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "p"}), encoding="utf-8")
    (tmp_path / "math.js").write_text(
        "function add(a, b) { return a + b; }\n"
        "const mul = (a, b) => a * b;\n"
        "module.exports = { add, mul };\n",
        encoding="utf-8",
    )
    gaps = scan_gaps(tmp_path, make_manifest())

    assert len(gaps) == 1
    assert gaps[0].file == "math.js"
    assert set(gaps[0].untested) == {"add", "mul"}


def test_export_assigned_names_detected(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "p"}), encoding="utf-8")
    (tmp_path / "util.js").write_text(
        "function helper() {}\nmodule.exports.helper = helper;\nexports.extra = 42;\n",
        encoding="utf-8",
    )
    gaps = scan_node_gaps(tmp_path)

    names = {name for g in gaps for name in g.untested}
    assert names == {"helper", "extra"}


def test_tested_export_excluded(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "p"}), encoding="utf-8")
    (tmp_path / "math.js").write_text(
        "function add(a, b) { return a + b; }\nfunction sub(a, b) { return a - b; }\n"
        "module.exports = { add, sub };\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "add.test.js").write_text(
        "const { add } = require('../math');\ntest('add', () => {});\n", encoding="utf-8"
    )
    gaps = scan_node_gaps(tmp_path)

    assert len(gaps) == 1
    assert gaps[0].untested == ["sub"]


def test_test_files_themselves_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"name": "p"}), encoding="utf-8")
    (tmp_path / "sum.test.js").write_text(
        "function unreferenced_helper() {}\nmodule.exports = { unreferenced_helper };\n",
        encoding="utf-8",
    )
    assert scan_node_gaps(tmp_path) == []
