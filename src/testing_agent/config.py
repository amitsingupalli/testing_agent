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


class EndpointCheck(BaseModel):
    """One HTTP smoke check for the system layer."""

    path: str = "/"
    expected_status: int = 200


class SystemConfig(BaseModel):
    """Settings for the system layer: boot the app, healthcheck, smoke checks."""

    target_url: str = "http://127.0.0.1:8901"
    boot_command: str | None = None  # e.g. "npm start" or "node server.js"
    boot_timeout_seconds: int = Field(default=60, ge=1)
    healthcheck_path: str = "/health"
    healthcheck_expected_status: int = 200
    endpoints: list[EndpointCheck] = Field(default_factory=lambda: [EndpointCheck(path="/")])


class PerformanceConfig(BaseModel):
    """Settings for the performance layer."""

    target_url: str | None = None  # no target -> performance layer reports NO TESTS
    duration_seconds: int = Field(default=5, ge=1)
    connections: int = Field(default=10, ge=1)
    max_latency_p975_ms: float | None = None  # autocannon latency ceiling
    min_requests_per_second: float | None = None
    k6_script: str | None = None  # path to a k6 script; enables the k6 adapter
    run_lighthouse: bool = False  # Lighthouse is heavy; opt-in
    min_lighthouse_score: float | None = None  # 0-100


class SecurityConfig(BaseModel):
    """Thresholds for the security layer."""

    max_critical: int = 0
    max_high: int = 0
    max_total: int | None = None
    run_bandit: bool = True
    use_semgrep_auto: bool = False  # auto rules need network; opt-in


class ProjectConfig(BaseModel):
    """Persisted project configuration (written by `testing-agent init`)."""

    root: str
    timeout_seconds: int = Field(default=300, ge=1)
    gate: GatePolicy = Field(default_factory=GatePolicy)
    system: SystemConfig = Field(default_factory=SystemConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
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
