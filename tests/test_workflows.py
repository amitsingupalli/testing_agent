"""Tests for GitHub Actions workflow validity."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_ci_workflow_structure() -> None:
    data = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))

    # YAML 1.1 parses bare `on:` as boolean True
    trigger = data.get("on", data.get(True))
    assert trigger is not None
    assert set(trigger["push"]["branches"]) == {"main"}
    jobs = data["jobs"]
    assert "self-tests" in jobs and "demo-runs" in jobs
    for job in jobs.values():
        assert job["runs-on"] in ("${{ matrix.os }}", "ubuntu-latest", "windows-latest")
        steps = job["steps"]
        assert steps[0]["uses"].startswith("actions/checkout@")
        run_steps = [s for s in steps if "run" in s]
        assert run_steps, "job has no run steps"


def test_ci_workflow_demo_layers() -> None:
    data = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))

    run_commands = [
        step["run"] for job in data["jobs"].values() for step in job["steps"] if "run" in step
    ]
    joined = "\n".join(run_commands)
    assert "--type unit" in joined
    assert "--type security" in joined
    assert "--type system" in joined
    assert "--type regression" in joined
    assert "--junit" in joined


def test_action_yml_structure() -> None:
    data = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert data["name"] == "testing-agent"
    assert data["runs"]["using"] == "composite"
    steps = data["runs"]["steps"]
    inputs = data["inputs"]
    assert inputs["path"]["default"] == "."
    assert inputs["type"]["default"] == "unit"
    uses = [step.get("uses", "") for step in steps]
    assert any(u.startswith("astral-sh/setup-uv@") for u in uses)
    assert any(u.startswith("actions/upload-artifact@") for u in uses)
    # every composite step must declare a shell
    for step in steps:
        if "run" in step:
            assert step.get("shell"), f"missing shell on step: {step['name']}"
