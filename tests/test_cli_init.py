"""Tests for the CLI init command (typer CliRunner)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from testing_agent.cli import app

runner = CliRunner()


def make_node_app(root: Path) -> None:
    (root / "package.json").write_text(
        '{"name": "demo-app", "version": "1.0.0", "scripts": {"test": "node --test"}}'
    )


def test_init_prefills_system_settings_for_single_node_app(tmp_path) -> None:
    make_node_app(tmp_path)

    result = runner.invoke(app, ["init", "--path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    config = json.loads((tmp_path / ".testing-agent.json").read_text(encoding="utf-8"))
    assert config["system"]["boot_command"] == "npm start"
    assert config["system"]["target_url"] == "http://127.0.0.1:3000"
    assert config["performance"]["target_url"] == "http://127.0.0.1:3000"
    assert config["system"]["boot_timeout_seconds"] >= 1


def test_init_does_not_overwrite_existing_config(tmp_path) -> None:
    make_node_app(tmp_path)
    first = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert first.exit_code == 0

    # second init must not clobber user-edited boot command
    config = json.loads((tmp_path / ".testing-agent.json").read_text(encoding="utf-8"))
    config["system"]["boot_command"] = "node custom.js"
    (tmp_path / ".testing-agent.json").write_text(json.dumps(config), encoding="utf-8")

    second = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert second.exit_code == 0
    reloaded = json.loads((tmp_path / ".testing-agent.json").read_text(encoding="utf-8"))
    assert reloaded["system"]["boot_command"] == "node custom.js"


def test_init_no_prefill_for_empty_dir(tmp_path) -> None:
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])

    assert result.exit_code == 0
    config = json.loads((tmp_path / ".testing-agent.json").read_text(encoding="utf-8"))
    assert config["system"]["boot_command"] is None


def test_init_no_prefill_for_python_app(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n[tool.pytest.ini_options]\n'
    )

    result = runner.invoke(app, ["init", "--path", str(tmp_path)])

    assert result.exit_code == 0
    config = json.loads((tmp_path / ".testing-agent.json").read_text(encoding="utf-8"))
    assert config["system"]["boot_command"] is None
