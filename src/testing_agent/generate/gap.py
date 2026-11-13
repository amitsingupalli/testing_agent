"""Test-gap scanners: find source symbols with no test references."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from testing_agent.detect.models import ProjectManifest, Stack
from testing_agent.generate.models import SourceFileGaps, SourceSymbol

SKIP_DIRECTORY_NAMES = {
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    "__pycache__",
    ".git",
    "examples",
    ".testing-agent",
    "site-packages",
    ".pytest_cache",
}

_TEST_DIRECTORY_NAMES = {"tests", "test", "__tests__", "e2e"}


def _is_test_path(relative_parts: tuple[str, ...], name: str) -> bool:
    if any(part in _TEST_DIRECTORY_NAMES for part in relative_parts[:-1]):
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name or name.startswith("test-"):
        return True
    return False


def _iter_source_files(root: Path, suffixes: tuple[str, ...]):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        relative = path.relative_to(root)
        if any(
            part in SKIP_DIRECTORY_NAMES or part.startswith(".")
            for part in relative.parts[:-1]
        ):
            continue
        if _is_test_path(relative.parts, relative.name):
            continue
        yield path, relative


def _collect_test_corpus(root: Path) -> str:
    """Concatenate every test file's text so symbol names can be searched."""
    chunks: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRECTORY_NAMES for part in relative.parts[:-1]):
            continue
        if not _is_test_path(relative.parts, relative.name):
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def _symbol_tested(name: str, corpus: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", corpus) is not None


def _python_symbols(path: Path) -> list[SourceSymbol]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return []

    symbols: list[SourceSymbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.append(SourceSymbol(name=node.name, kind="function", line=node.lineno))
        elif isinstance(node, ast.ClassDef):
            symbols.append(SourceSymbol(name=node.name, kind="class", line=node.lineno))
    return symbols


def scan_python_gaps(root: Path) -> list[SourceFileGaps]:
    """Scan .py sources (AST-based) for symbols never referenced in tests."""
    corpus = _collect_test_corpus(root)
    file_gaps: list[SourceFileGaps] = []
    for path, relative in _iter_source_files(root, (".py",)):
        symbols = _python_symbols(path)
        if not symbols:
            continue
        tested = [s.name for s in symbols if _symbol_tested(s.name, corpus)]
        untested = [s.name for s in symbols if s.name not in tested]
        if untested:
            file_gaps.append(
                SourceFileGaps(
                    file=str(relative).replace("\\", "/"),
                    symbols=symbols,
                    tested=tested,
                    untested=untested,
                )
            )
    return file_gaps


def scan_gaps(root: Path, manifest: ProjectManifest) -> list[SourceFileGaps]:
    """Dispatch to the right scanner for the manifest's stack."""
    if manifest.stack == Stack.PYTHON:
        return scan_python_gaps(root)
    return []
