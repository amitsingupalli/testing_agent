"""Diff-aware test selection: map changed source files to candidate test files."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

# file extensions treated as test files, per stack convention
_PYTHON_TEST_PATTERNS = ("test_*.py", "*_test.py")
_NODE_TEST_PATTERNS = ("*.test.js", "*.test.ts", "*.test.mjs", "*.test.cjs", "*.test.jsx", "*.test.tsx", "*.spec.js", "*.spec.ts", "*.spec.mjs", "*.spec.tsx", "*.spec.jsx")

# change of these files invalidates the whole selection -> run everything
_FULL_RUN_TRIGGERS = (
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements*.txt",
    "uv.lock",
    "Pipfile",
    "setup.py",
    "setup.cfg",
    "tsconfig.json",
    ".github/workflows/*",
)


@dataclass
class Selection:
    """Result of diff-aware selection for one manifest."""

    mode: str  # "all" | "affected" | "none"
    reason: str = ""
    changed_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)


def is_test_file(path: str) -> bool:
    """Whether a repo-relative path looks like a test file (any stack)."""
    name = Path(path).name
    lowered = name.lower()
    for pattern in _PYTHON_TEST_PATTERNS:
        if fnmatch.fnmatch(lowered, pattern):
            return True
    for pattern in _NODE_TEST_PATTERNS:
        if fnmatch.fnmatch(lowered, pattern):
            return True
    return "__tests__" in Path(path).parts


def is_full_run_trigger(path: str) -> bool:
    """Whether a changed file is a config/dependency file that forces a full run."""
    posix = path.replace("\\", "/")
    for pattern in _FULL_RUN_TRIGGERS:
        if fnmatch.fnmatch(posix, pattern) or posix.endswith("/" + pattern):
            return True
    return False


def candidate_test_paths(changed_file: str) -> list[str]:
    """Repo-relative test paths that plausibly test a changed source file.

    Pure path algebra (no fs access): covers mirrored layouts, co-located
    tests, and the python/node naming conventions.
    """
    posix = changed_file.replace("\\", "/")
    if is_test_file(posix):
        return [posix]

    source = Path(posix)
    stem = source.stem
    suffix = source.suffix  # .py / .js / .ts / ...
    parts = list(source.parts)

    # strip conventional source roots to get the "module path"
    module_parts = parts
    for root_dir in ("src", "lib", "app", "source"):
        if module_parts and module_parts[0] == root_dir:
            module_parts = module_parts[1:]
            break

    if not module_parts:
        return []

    candidates: list[str] = []

    # python-style names: test_<stem>.py
    if suffix == ".py":
        test_name = f"test_{stem}.py"
        candidates.append(f"tests/{test_name}")
        candidates.append(f"tests/unit/{test_name}")
        # mirrored subpath: src/utils/str.py -> tests/unit/utils/test_str.py
        if len(module_parts) > 1:
            mirrored = "/".join(module_parts[:-1])
            candidates.append(f"tests/unit/{mirrored}/{test_name}")
        # co-located
        co_dir = "/".join(parts[:-1])
        candidates.append(f"{co_dir}/{test_name}" if co_dir else test_name)
        candidates.append(f"{co_dir}/test_{stem}.py" if co_dir else f"test_{stem}.py")
    else:
        for test_pattern in ("test", "spec"):
            ext = suffix or ".js"
            test_name = f"{stem}.{test_pattern}{ext}"
            candidates.append(f"tests/unit/{test_name}")
            candidates.append(f"tests/{test_name}")
            if len(module_parts) > 1:
                mirrored = "/".join(module_parts[:-1])
                candidates.append(f"tests/unit/{mirrored}/{test_name}")
            # __tests__ co-location: src/utils/str.js -> src/utils/__tests__/str.test.js
            co_dir = "/".join(parts[:-1])
            candidates.append(f"{co_dir}/__tests__/{test_name}" if co_dir else f"__tests__/{test_name}")

    # de-duplicate, preserve order
    seen: set[str] = set()
    unique = []
    for candidate in candidates:
        normalized = candidate.replace("\\", "/")
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def select_tests(
    changed_files: list[str],
    manifest_directory: str = "",
    check_exists: bool = True,
    root: Path | None = None,
) -> Selection:
    """Select which test files a regression run should execute.

    Returns mode "all" (run everything: no diff info, or a config/dependency
    file changed), "affected" (candidate paths that exist on disk), or "none"
    (changed files exist but map to no existing tests).
    """
    changed = [f.replace("\\", "/") for f in changed_files if f]

    if not changed:
        return Selection(mode="all", reason="no changed files known — running everything", changed_files=[])

    if any(is_full_run_trigger(path) for path in changed):
        triggers = [p for p in changed if is_full_run_trigger(p)]
        return Selection(
            mode="all",
            reason=f"config/dependency change: {', '.join(triggers[:3])}",
            changed_files=changed,
        )

    manifest_prefix = f"{manifest_directory.replace(chr(92), '/')}/" if manifest_directory else ""
    matched: list[str] = []
    seen: set[str] = set()
    for path in changed:
        # scoped to the manifest's subdirectory for monorepos
        scoped = path
        if manifest_prefix and scoped.startswith(manifest_prefix):
            scoped = scoped[len(manifest_prefix):]
        elif manifest_prefix:
            # change outside this manifest's directory doesn't affect it
            continue
        for candidate in candidate_test_paths(scoped):
            if candidate in seen:
                continue
            seen.add(candidate)
            if check_exists and root is not None:
                if (root / manifest_directory / candidate).is_file():
                    matched.append(candidate)
            else:
                matched.append(candidate)

    if matched:
        return Selection(
            mode="affected",
            reason=f"{len(changed)} changed file(s) map to {len(matched)} test file(s)",
            changed_files=changed,
            test_files=sorted(matched),
        )
    return Selection(
        mode="none",
        reason="changed files map to no existing test files",
        changed_files=changed,
    )
