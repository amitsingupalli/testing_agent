"""Tests for backends, prompts, and the gap manifest writer."""

from __future__ import annotations

from pathlib import Path

from testing_agent.generate.backends import ManifestBackend, extract_code_block
from testing_agent.generate.manifest import write_gap_manifest
from testing_agent.generate.models import GapManifest, GenerationTarget, SourceFileGaps
from testing_agent.generate.opencode_backend import OpenCodeBackend
from testing_agent.generate.prompts import build_failure_feedback, build_generation_prompt


def test_extract_code_block_python_fence() -> None:
    text = "Sure!\n```python\nimport pytest\n```\nDone."
    assert extract_code_block(text) == "import pytest\n"


def test_extract_code_block_no_fence_returns_all() -> None:
    assert extract_code_block("def test_x():\n    pass").strip().startswith("def test_x")


def test_manifest_backend_unavailable_for_generation() -> None:
    import pytest

    backend = ManifestBackend()
    assert backend.is_available()
    with pytest.raises(Exception):
        backend.generate(Path("."), GenerationTarget(source_file="a.py", untested=["f"], suggested_test_file="t.py"), "pytest", 10)


def test_build_generation_prompt_contains_symbols_and_source(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    target = GenerationTarget(
        source_file="calc.py",
        untested=["add"],
        suggested_test_file="tests/unit/test_calc_generated.py",
    )
    prompt = build_generation_prompt(tmp_path, target, "pytest")

    assert "`add`" in prompt
    assert "calc.py" in prompt
    assert "pytest" in prompt
    assert "tests/unit/test_calc_generated.py" in prompt


def test_build_generation_prompt_includes_failure_feedback(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    target = GenerationTarget(source_file="calc.py", untested=["add"], suggested_test_file="t.py")
    feedback = build_failure_feedback([("test_add", "assert 2 == 3")])
    prompt = build_generation_prompt(tmp_path, target, "pytest", failure_feedback=feedback)

    assert "test_add" in prompt
    assert "assert 2 == 3" in prompt


def test_opencode_backend_not_available_when_missing(monkeypatch) -> None:
    import testing_agent.generate.opencode_backend as module

    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert OpenCodeBackend().is_available() is False


def test_write_gap_manifest_creates_files(tmp_path: Path) -> None:
    manifest = GapManifest(
        root=str(tmp_path),
        files=[
            SourceFileGaps(
                file="calc.py",
                symbols=[{"name": "add", "kind": "function", "line": 1}],
                tested=[],
                untested=["add"],
            )
        ],
    )
    markdown_path, json_path = write_gap_manifest(tmp_path, manifest)

    assert markdown_path.is_file() and json_path.is_file()
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "calc.py" in markdown
    assert "`add`" in markdown
