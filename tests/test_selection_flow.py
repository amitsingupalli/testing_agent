"""Integration tests for diff-aware selection in the CLI and pytest adapter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from testing_agent.cli import app
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.runners.pytest_unit import PytestRunner
from testing_agent.runners.base import TestType

runner = CliRunner()


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _init_git_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")


def make_node_project(root: Path) -> None:
    (root / "package.json").write_text(
        json.dumps(
            {"name": "sel-demo", "version": "1.0.0", "scripts": {"test": "node --test"}}
        )
    )
    (root / "src").mkdir()
    (root / "src" / "app.js").write_text("module.exports.add = (a, b) => a + b;\n")
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "app.test.js").write_text(
        "const test = require('node:test');\n"
        "const assert = require('node:assert');\n"
        "test('add', () => { assert.equal(1 + 1, 2); });\n"
    )


def test_regression_selection_affected(tmp_path: Path) -> None:
    make_node_project(tmp_path)
    _init_git_repo(tmp_path)

    # modify a mapped source file
    (tmp_path / "src" / "app.js").write_text("module.exports.add = (a, b) => a + b + 0;\n")

    result = runner.invoke(app, ["run", "--path", str(tmp_path), "--type", "regression"])

    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / ".testing-agent" / "last-report.json").read_text())
    selection = report.get("test_selection")
    assert selection is not None
    assert selection["mode"] == "affected"
    assert selection["test_files"] == ["tests/unit/app.test.js"]
    # only the mapped test file ran
    node_result = next(r for r in report["results"] if r["runner"] == "node")
    assert node_result["passed"] == 1
    assert "app.test.js" in node_result["command"]


def test_regression_selection_none_forces_note(tmp_path: Path) -> None:
    make_node_project(tmp_path)
    _init_git_repo(tmp_path)

    # change a file with no mapped tests, force --select affected
    (tmp_path / "src" / "orphan.js").write_text("module.exports = 1;\n")

    result = runner.invoke(
        app,
        ["run", "--path", str(tmp_path), "--type", "regression", "--select", "affected"],
    )

    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / ".testing-agent" / "last-report.json").read_text())
    node_result = next(r for r in report["results"] if r["runner"] == "node")
    assert node_result["no_tests"] is True
    assert "diff-aware selection" in (node_result["note"] or "")
    assert "--select all" in (node_result["note"] or "")


def test_regression_select_all_runs_everything(tmp_path: Path) -> None:
    make_node_project(tmp_path)
    _init_git_repo(tmp_path)

    (tmp_path / "src" / "orphan.js").write_text("module.exports = 1;\n")

    result = runner.invoke(
        app, ["run", "--path", str(tmp_path), "--type", "regression", "--select", "all"]
    )

    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / ".testing-agent" / "last-report.json").read_text())
    node_result = next(r for r in report["results"] if r["runner"] == "node")
    assert node_result["no_tests"] is False
    assert node_result["passed"] == 1
    assert report.get("test_selection") is None


def test_pytest_adapter_narrowed_files(tmp_path: Path) -> None:
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "test_a.py").write_text(
        "def test_a():\n    assert True\n"
    )
    (tmp_path / "tests" / "unit" / "test_b.py").write_text(
        "def test_b():\n    assert True\n"
    )

    manifest = ProjectManifest(stack=Stack.PYTHON, test_runner="pytest")
    result = PytestRunner().run(
        manifest,
        tmp_path,
        TestType.UNIT,
        timeout_seconds=120,
        test_files=["tests/unit/test_a.py"],
    )

    assert result.passed == 1
    assert result.failed == 0
    assert "test_a.py" in result.command
    assert "test_b.py" not in result.command
