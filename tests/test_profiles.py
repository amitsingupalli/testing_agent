"""Tests for gate profiles and policy resolution."""

from __future__ import annotations

import pytest

from testing_agent.config import (
    GatePolicy,
    ProjectConfig,
    default_profiles,
    resolve_policy,
)


def test_default_profiles_contents() -> None:
    profiles = default_profiles()

    assert set(profiles) == {"dev", "ci", "release"}
    assert profiles["dev"].require_types == ["unit"]
    assert profiles["ci"].require_types == ["unit", "integration"]
    assert profiles["release"].require_types == ["unit", "integration", "security", "performance"]
    assert profiles["release"].fail_on_missing_runner is True
    assert profiles["dev"].fail_on_missing_runner is False


def test_config_has_profiles_by_default() -> None:
    config = ProjectConfig(root=".")

    assert set(config.profiles) == {"dev", "ci", "release"}
    assert config.active_profile is None


def test_resolve_policy_no_profile_returns_base_gate() -> None:
    config = ProjectConfig(root=".", gate=GatePolicy(min_pass_rate=0.5))

    assert resolve_policy(config, None) is config.gate


def test_resolve_policy_explicit_profile() -> None:
    config = ProjectConfig(root=".", active_profile=None)

    assert resolve_policy(config, "release") is config.profiles["release"]
    assert resolve_policy(config, "ci") is config.profiles["ci"]


def test_resolve_policy_active_profile_fallback() -> None:
    config = ProjectConfig(root=".", active_profile="ci")

    assert resolve_policy(config, None) is config.profiles["ci"]


def test_resolve_policy_explicit_beats_active() -> None:
    config = ProjectConfig(root=".", active_profile="ci")

    assert resolve_policy(config, "release") is config.profiles["release"]


def test_resolve_policy_unknown_profile_raises() -> None:
    config = ProjectConfig(root=".", active_profile=None)

    with pytest.raises(KeyError) as excinfo:
        resolve_policy(config, "staging")
    assert "staging" in str(excinfo.value)
    assert "dev" in str(excinfo.value)
