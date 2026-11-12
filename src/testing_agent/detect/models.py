"""Data models shared by stack detection."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Stack(str, Enum):
    """Language/runtime ecosystem of a project."""

    NODE = "node"
    PYTHON = "python"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class PackageManager(str, Enum):
    """Package manager inferred from lockfiles."""

    NPM = "npm"
    PNPM = "pnpm"
    YARN = "yarn"
    UV = "uv"
    PIP = "pip"
    GO = "go"
    CARGO = "cargo"
    NONE = "none"


class ProjectManifest(BaseModel):
    """One detected project (root or a subdirectory of a monorepo)."""

    directory: str = ""  # "" for the root, else relative subdirectory
    stack: Stack = Stack.UNKNOWN
    package_manager: PackageManager = PackageManager.NONE
    name: str | None = None
    test_runner: str | None = None  # e.g. "vitest", "jest", "node", "pytest", "go", "cargo"


class DetectionResult(BaseModel):
    """Everything detection learned about a target directory."""

    root: str
    manifests: list[ProjectManifest] = Field(default_factory=list)
    is_monorepo: bool = False
