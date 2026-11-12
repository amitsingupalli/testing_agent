"""Detection of Go and Rust projects (go.mod / Cargo.toml)."""

from __future__ import annotations

import re
from pathlib import Path

from testing_agent.detect.models import PackageManager, ProjectManifest, Stack

_MODULE_PATTERN = re.compile(r"^module\s+(\S+)", re.MULTILINE)


def detect_go(directory: Path) -> ProjectManifest | None:
    """Return a manifest when the directory contains a go.mod."""
    go_mod = directory / "go.mod"
    if not go_mod.is_file():
        return None
    try:
        content = go_mod.read_text(encoding="utf-8-sig")
    except OSError:
        content = ""

    match = _MODULE_PATTERN.search(content)
    return ProjectManifest(
        directory="",
        stack=Stack.GO,
        package_manager=PackageManager.GO,
        name=match.group(1) if match else None,
        test_runner="go",
    )


def detect_rust(directory: Path) -> ProjectManifest | None:
    """Return a manifest when the directory contains a Cargo.toml."""
    cargo_toml = directory / "Cargo.toml"
    if not cargo_toml.is_file():
        return None
    name: str | None = None
    try:
        content = cargo_toml.read_text(encoding="utf-8-sig")
        match = re.search(r'^name\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            name = match.group(1)
    except OSError:
        pass

    return ProjectManifest(
        directory="",
        stack=Stack.RUST,
        package_manager=PackageManager.CARGO,
        name=name,
        test_runner="cargo",
    )
