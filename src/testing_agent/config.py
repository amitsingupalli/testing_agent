"""Project configuration for testing-agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFIG_FILE_NAME = ".testing-agent.json"


class GatePolicy(BaseModel):
    """Which checks the gate enforces before a run is allowed to pass."""

    require_types: list[str] = Field(default_factory=lambda: ["unit"])
    min_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    fail_on_missing_runner: bool = False
    fail_on_no_tests: bool = False


class ProjectConfig(BaseModel):
    """Persisted project configuration (written by `testing-agent init`)."""

    root: str
    timeout_seconds: int = Field(default=300, ge=1)
    gate: GatePolicy = Field(default_factory=GatePolicy)
    runner_overrides: dict[str, str] = Field(default_factory=dict)


def config_path(root: Path) -> Path:
    """Path of the config file for a project root."""
    return root / CONFIG_FILE_NAME


def load_config(root: Path) -> ProjectConfig | None:
    """Load the config for a project root, or None when absent/invalid."""
    path = config_path(root)
    if not path.is_file():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
        return ProjectConfig.model_validate(data)
    except Exception:  # noqa: BLE001 - config is optional; never crash the CLI
        return None


def save_config(root: Path, config: ProjectConfig) -> Path:
    """Write the config for a project root and return the file path."""
    path = config_path(root)
    path.write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
