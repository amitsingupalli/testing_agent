"""Models for test-gap scanning and generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceSymbol(BaseModel):
    """A top-level function or class found in a source file."""

    name: str
    kind: str = "function"  # "function" | "class"
    line: int = 0


class SourceFileGaps(BaseModel):
    """Test-gap analysis for one source file."""

    file: str  # relative to the project root
    symbols: list[SourceSymbol] = Field(default_factory=list)
    tested: list[str] = Field(default_factory=list)
    untested: list[str] = Field(default_factory=list)


class GapManifest(BaseModel):
    """Everything the scanner believes needs tests."""

    root: str
    files: list[SourceFileGaps] = Field(default_factory=list)

    @property
    def gap_count(self) -> int:
        return sum(len(file_gaps.untested) for file_gaps in self.files)


class GenerationTarget(BaseModel):
    """One source file the generation backend should cover."""

    source_file: str
    untested: list[str] = Field(default_factory=list)
    suggested_test_file: str


class GenerationOutcome(BaseModel):
    """Result of generating tests for one target."""

    backend: str
    source_file: str
    test_file: str | None = None
    rounds: int = 0
    success: bool = False
    error: str | None = None
    note: str | None = None


class GenerationReport(BaseModel):
    """Aggregate result of one `testing-agent generate` run."""

    backend: str
    outcomes: list[GenerationOutcome] = Field(default_factory=list)
    manifest_path: str | None = None

    @property
    def all_success(self) -> bool:
        return bool(self.outcomes) and all(outcome.success for outcome in self.outcomes)
