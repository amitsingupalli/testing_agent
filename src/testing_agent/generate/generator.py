"""Generation orchestrator: scan gaps, pick a backend, generate, verify, retry."""

from __future__ import annotations

from pathlib import Path

from testing_agent.detect import detect_project
from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.generate.backends import Backend, GenerationError, ManifestBackend
from testing_agent.generate.gap import scan_gaps
from testing_agent.generate.llm_backends import AnthropicBackend, OpenAIBackend
from testing_agent.generate.manifest import write_gap_manifest
from testing_agent.generate.models import (
    GapManifest,
    GenerationOutcome,
    GenerationReport,
    GenerationTarget,
    SourceFileGaps,
)
from testing_agent.generate.opencode_backend import OpenCodeBackend
from testing_agent.generate.prompts import build_failure_feedback, suggested_test_file
from testing_agent.runners import select_runner
from testing_agent.runners.base import RunResult, TestType

_MAX_FILES_DEFAULT = 3


def select_backend(explicit: str | None = None) -> Backend:
    """Pick a backend by explicit id or via the auto fallback chain."""
    if explicit and explicit != "auto":
        backends = {"opencode": OpenCodeBackend(), "anthropic": AnthropicBackend(), "openai": OpenAIBackend(), "manifest": ManifestBackend()}
        backend = backends[explicit]
        if not backend.is_available():
            raise GenerationError(f"backend '{explicit}' is not available in this environment")
        return backend

    for candidate in (OpenCodeBackend(), AnthropicBackend(), OpenAIBackend()):
        if candidate.is_available():
            return candidate
    return ManifestBackend()


def _framework_for(manifest: ProjectManifest) -> str:
    return "pytest" if manifest.stack == Stack.PYTHON else "node:test"


def _targets_for(
    manifest: ProjectManifest,
    file_gaps: list[SourceFileGaps],
    max_files: int,
) -> list[GenerationTarget]:
    framework = _framework_for(manifest)
    targets: list[GenerationTarget] = []
    for file_gap in file_gaps:
        if len(targets) >= max_files:
            break
        targets.append(
            GenerationTarget(
                source_file=file_gap.file,
                untested=file_gap.untested,
                suggested_test_file=suggested_test_file(file_gap.file, framework),
            )
        )
    return targets


def _write_test_file(root: Path, relative_path: str, code: str) -> Path:
    if "_generated" not in Path(relative_path).name:
        raise GenerationError(f"refusing to write non-generated test file name: {relative_path}")
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(code, encoding="utf-8")
    return destination


def _generate_with_verification(
    root: Path,
    manifest: ProjectManifest,
    target: GenerationTarget,
    backend: Backend,
    timeout_seconds: int,
    feedback_rounds: int,
) -> GenerationOutcome:
    framework = _framework_for(manifest)
    runner = select_runner(manifest, TestType.UNIT)
    feedback: str | None = None
    last_error: str | None = None

    for round_number in range(1, feedback_rounds + 2):
        try:
            code = backend.generate(root, target, framework, timeout_seconds, feedback)
            if getattr(backend, "writes_files", False):
                # The backend wrote the file itself (e.g. the opencode agent).
                test_file = root / target.suggested_test_file
                if not test_file.is_file():
                    raise GenerationError(
                        f"backend '{backend.id}' did not create {target.suggested_test_file}"
                    )
            else:
                test_file = _write_test_file(root, target.suggested_test_file, code)
        except GenerationError as error:
            return GenerationOutcome(
                backend=backend.id,
                source_file=target.source_file,
                test_file=target.suggested_test_file,
                rounds=round_number - 1,
                success=False,
                error=str(error),
            )

        result: RunResult | None = None
        if runner is not None:
            result = runner.run(manifest, root, TestType.UNIT, timeout_seconds)
        if result is None or (result.success and not result.no_tests):
            return GenerationOutcome(
                backend=backend.id,
                source_file=target.source_file,
                test_file=str(test_file),
                rounds=round_number,
                success=True,
            )

        last_error = f"suite failed after generation (exit {result.exit_code})"
        feedback = build_failure_feedback(
            [(failure.name, failure.message) for failure in result.failures]
        )

    return GenerationOutcome(
        backend=backend.id,
        source_file=target.source_file,
        test_file=str(test_file),
        rounds=feedback_rounds + 1,
        success=False,
        error=last_error,
        note="generated tests still failing after retry rounds",
    )


def generate_tests(
    root: Path,
    backend_id: str | None = "auto",
    max_files: int = _MAX_FILES_DEFAULT,
    timeout_seconds: int = 300,
    feedback_rounds: int = 2,
) -> GenerationReport:
    """Run the full generate → verify → retry loop for a project."""
    root = root.resolve()
    backend = select_backend(backend_id)
    detection = detect_project(root)

    all_gaps: list[tuple[ProjectManifest, list[SourceFileGaps]]] = []
    for manifest in detection.manifests:
        gaps = [fg for fg in scan_gaps(root, manifest) if fg.untested]
        if gaps:
            all_gaps.append((manifest, gaps))

    if not all_gaps:
        return GenerationReport(
            backend=backend.id,
            manifest_path=None,
            outcomes=[
                GenerationOutcome(
                    backend=backend.id,
                    source_file="(project)",
                    success=True,
                    note="no test gaps found — every scanned symbol has a test reference",
                )
            ],
        )

    if isinstance(backend, ManifestBackend):
        gap_manifest = GapManifest(
            root=str(root),
            files=[fg for _, gaps in all_gaps for fg in gaps],
        )
        markdown_path, _json_path = write_gap_manifest(root, gap_manifest)
        outcomes = [
            GenerationOutcome(
                backend=backend.id,
                source_file=fg.file,
                success=True,
                note="no LLM backend available — see .testing-agent/gap-manifest.md",
            )
            for _, gaps in all_gaps
            for fg in gaps[:max_files]
        ]
        return GenerationReport(backend=backend.id, outcomes=outcomes, manifest_path=str(markdown_path))

    outcomes: list[GenerationOutcome] = []
    for manifest, gaps in all_gaps:
        remaining = max_files - len(outcomes)
        if remaining <= 0:
            break
        targets = _targets_for(manifest, gaps, remaining)
        for target in targets:
            outcomes.append(
                _generate_with_verification(
                    root, manifest, target, backend, timeout_seconds, feedback_rounds
                )
            )

    return GenerationReport(backend=backend.id, outcomes=outcomes, manifest_path=None)


def write_generation_report(root: Path, report: GenerationReport) -> Path:
    """Persist last-generation.json."""
    directory = Path(root) / ".testing-agent"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "last-generation.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
