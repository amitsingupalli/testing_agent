"""Prompt construction for test generation backends."""

from __future__ import annotations

from pathlib import Path

from testing_agent.generate.models import GenerationTarget

_MAX_SOURCE_CHARS = 8000

_FRAMEWORK_INSTRUCTIONS = {
    "pytest": (
        "Use pytest (plain functions, no classes). "
        "The test file MUST be importable from the project root: "
        "import the module under test exactly as a script in the project root would."
    ),
    "node:test": (
        "Use Node's built-in runner (`node:test` + `node:assert/strict`, CommonJS `require`). "
        "Require the source module with the correct relative path from the test file's location."
    ),
}


def suggested_test_file(source_file: str, framework: str) -> str:
    """Naming convention for generated test files (always *_generated*)."""
    stem = Path(source_file).stem
    if framework == "pytest":
        return f"tests/unit/test_{stem}_generated.py"
    return f"tests/unit/{stem}_generated.test.js"


def build_generation_prompt(
    root: Path,
    target: GenerationTarget,
    framework: str,
    failure_feedback: str | None = None,
) -> str:
    """Build the instruction prompt handed to a generation backend."""
    source_path = root / target.source_file
    try:
        source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        source_text = "(source file could not be read — explore the repository)"
    if len(source_text) > _MAX_SOURCE_CHARS:
        source_text = source_text[:_MAX_SOURCE_CHARS] + "\n# ... (truncated)"

    symbols = ", ".join(f"`{name}`" for name in target.untested)
    instructions = _FRAMEWORK_INSTRUCTIONS.get(framework, framework)

    lines = [
        "You are writing tests for an existing project. Follow these rules exactly:",
        f"1. Create or overwrite ONLY this file: `{target.suggested_test_file}`",
        f"2. Cover these untested symbols from `{target.source_file}`: {symbols}",
        f"3. Framework: {instructions}",
        "4. Test public behavior only — no mocking of the code under test, no network.",
        "5. Every test you write must pass against the current implementation.",
        "6. Do not modify any other file.",
        "",
        f"Source file `{target.source_file}`:",
        "```",
        source_text,
        "```",
        "",
        "Output ONLY the complete content of the test file (inside one code block).",
    ]
    if failure_feedback:
        lines += [
            "",
            "Your previous attempt produced these failing tests. Fix them:",
            failure_feedback,
        ]
    return "\n".join(lines)


def build_failure_feedback(failures: list[tuple[str, str | None]]) -> str:
    """Compact failure summary fed back into the next generation round."""
    lines = []
    for name, message in failures[:10]:
        lines.append(f"- {name}: {message or 'no message'}")
    return "\n".join(lines)
