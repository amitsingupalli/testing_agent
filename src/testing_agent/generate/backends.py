"""Generation backends: how test code gets produced.

Backends (in fallback order):
- opencode   — delegate to the `opencode run` non-interactive CLI
- anthropic  — direct Anthropic Messages API (ANTHROPIC_API_KEY)
- openai     — direct OpenAI Chat Completions API (OPENAI_API_KEY)
- manifest   — no LLM; write a gap manifest the host agent acts on
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from testing_agent.generate.models import GenerationTarget
from testing_agent.generate.prompts import extract_code_block  # re-exported for convenience

__all__ = ["Backend", "GenerationError", "ManifestBackend", "extract_code_block"]


class GenerationError(Exception):
    """Raised when a backend fails to produce usable test code."""


class Backend(ABC):
    """A test-code production strategy."""

    id: str = "unknown"
    # True when the backend writes the test file itself (orchestrator must
    # NOT overwrite it with parsed output — e.g. the opencode agent).
    writes_files: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run in the current environment."""

    @abstractmethod
    def generate(
        self,
        root: Path,
        target: GenerationTarget,
        framework: str,
        timeout_seconds: int,
        failure_feedback: str | None = None,
    ) -> str:
        """Return generated test-code text for the target.

        Raises GenerationError on failure.
        """


class ManifestBackend(Backend):
    """Fallback: produce nothing; the orchestrator writes the gap manifest."""

    id = "manifest"

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        root: Path,
        target: GenerationTarget,
        framework: str,
        timeout_seconds: int,
        failure_feedback: str | None = None,
    ) -> str:
        raise GenerationError("manifest backend does not generate code")
