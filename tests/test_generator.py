"""End-to-end tests for the generation orchestrator (manifest backend path)."""

from __future__ import annotations

import json
from pathlib import Path

from testing_agent.generate.backends import GenerationError
from testing_agent.generate.generator import generate_tests, select_backend, write_generation_report
from testing_agent.generate.models import GenerationTarget


def build_gap_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "p"\n[dependency-groups]\ndev = ["pytest>=8"]\n', encoding="utf-8"
    )
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()


def test_manifest_backend_written_when_no_llm(tmp_path: Path, monkeypatch) -> None:
    build_gap_project(tmp_path)
    # Force the fallback chain to land on the manifest backend
    import testing_agent.generate.generator as generator_module

    monkeypatch.setattr(generator_module, "select_backend", lambda explicit=None: generator_module.ManifestBackend())

    report = generate_tests(tmp_path, backend_id="auto")

    assert report.backend == "manifest"
    assert report.all_success is True
    assert report.manifest_path is not None and Path(report.manifest_path).is_file()
    markdown = Path(report.manifest_path).read_text(encoding="utf-8")
    assert "add" in markdown and "multiply" in markdown


def test_no_gaps_reports_clean(tmp_path: Path, monkeypatch) -> None:
    build_gap_project(tmp_path)
    (tmp_path / "tests" / "test_calc.py").write_text(
        "import calc\n\ndef test_all():\n    assert calc.add(1, 2) == 3\n    assert calc.multiply(2, 3) == 6\n",
        encoding="utf-8",
    )
    import testing_agent.generate.generator as generator_module

    monkeypatch.setattr(generator_module, "select_backend", lambda explicit=None: generator_module.ManifestBackend())

    report = generate_tests(tmp_path, backend_id="auto")

    assert report.manifest_path is None
    assert report.outcomes[0].success is True
    assert "no test gaps" in (report.outcomes[0].note or "")


def test_write_generation_report_persists(tmp_path: Path) -> None:
    from testing_agent.generate.models import GenerationOutcome, GenerationReport

    report = GenerationReport(
        backend="manifest",
        outcomes=[GenerationOutcome(backend="manifest", source_file="a.py", success=True)],
        manifest_path=None,
    )
    path = write_generation_report(tmp_path, report)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["backend"] == "manifest"
    assert data["outcomes"][0]["success"] is True


def test_select_backend_explicit_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        select_backend("does-not-exist")


def test_write_test_file_refuses_non_generated_names(tmp_path: Path) -> None:
    from testing_agent.generate.generator import _write_test_file

    import pytest

    with pytest.raises(GenerationError):
        _write_test_file(tmp_path, "tests/unit/test_calc.py", "x = 1\n")


def test_write_test_file_accepts_generated_names(tmp_path: Path) -> None:
    from testing_agent.generate.generator import _write_test_file

    path = _write_test_file(tmp_path, "tests/unit/test_calc_generated.py", "def test_x():\n    pass\n")
    assert path.is_file()


def test_generation_target_model_round_trip() -> None:
    target = GenerationTarget(source_file="a.py", untested=["f"], suggested_test_file="t.py")
    assert target.model_dump(mode="json")["untested"] == ["f"]
