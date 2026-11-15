# Changelog

All notable changes to `testing-agent` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/) (roughly); versions are tagged `v*` in git.

## [0.4.0] — Phase 4

### Added
- **Compatibility layer** — Playwright browser-matrix runner (`run --type compatibility`): parses `--reporter=json` output, per-project browser names, failure details, `--project` overrides via `compatibility.browsers`, `PLAYWRIGHT_BASE_URL` passthrough; self-skips without `playwright.config.*`.
- **Diff-aware test selection** (`run --type regression --select auto|all|affected`): maps changed files to candidate tests (mirrored/co-located layouts, python/node naming), forces full runs on config/dependency changes, reports selection in `test_selection` report section. pytest and node adapters honor narrowed file lists; vitest/jest note the fallback.
- **GitHub Actions CI** — matrix (ubuntu/windows) self-tests + live layer demos on every push/PR.
- **Reusable composite action** (`action.yml`) — inputs `path`, `type`, `profile`, `junit`, `version`; uploads `.testing-agent/` artifacts; `uvx testing-agent` resolution.
- **PyPI publish workflow** — tag-triggered (`v*`), OIDC trusted publishing, self-tests gate before publish.
- Build metadata for PyPI: license files, classifiers, project URLs, Python `>=3.11`.

## [0.3.0] — Phase 3

### Added
- **Security layer** — `npm audit --json` (Node; lockfile-gated, error-payload detection), `pip-audit` (Python), `bandit` source scanning, optional `semgrep` (requires `.semgrep.yml` or `use_semgrep_auto`); severity thresholds `max_critical`/`max_high`/`max_total`.
- **Performance layer** — `autocannon` (npx, latency p97.5 + RPS thresholds), `k6` (`--summary-export`), opt-in Lighthouse with score floor.
- **System layer** — boots the app (`system.boot_command`), polls `healthcheck_path`, smoke-checks `endpoints`, kills the process tree on teardown (taskkill /T with terminate/kill fallback), teardown log marker.
- **Gate profiles** — `dev` / `ci` / `release` with `--profile` flag and custom profiles in config; `release` fails on missing runners.
- **JUnit XML output** — `run --junit` writes `.testing-agent/junit-report.xml` for CI ingestion.
- **Combined summary** — cross-runner, per-type totals in JSON/Markdown/terminal reports.
- `init` pre-fills system/performance hints for single Node apps.
- `examples/webapp-demo` — zero-dependency HTTP server for system/performance demos.

## [0.2.0] — Phase 2

### Added
- **Test generation** — AST/regex gap scanning (Python + Node), backends `auto` → opencode CLI → Anthropic → OpenAI → gap manifest, generate → verify → retry loop, `*_generated.*` test files never touching hand-written tests, generation reports (JSON + Markdown).
- **opencode integration** — plugin (`testing_agent_run` / `testing_agent_detect` tools, background gate), `tester` subagent, skill; dogfooded in-repo under `.opencode/`.
- **Regression git context** — changed-file summary, test-vs-source classification in reports.
- `examples/python-demo` with intentional coverage gaps.

## [0.1.0] — Phase 1

### Added
- Stack detection (Node, Python, Go, Rust; root + one level deep for monorepos).
- Runner adapters: pytest, vitest, jest, Node built-in `node --test` (JUnit/aggregate JSON parsing, timeouts, full logs).
- Gate engine (required layers, pass-rate threshold, missing-runner policy).
- Reports: JSON, Markdown, rich terminal with failure details.
- CLI: `init`, `detect`, `run`, `report`, `generate`.
- `examples/node-demo`.

[unreleased]: https://github.com/amitsingupalli/testing_agent/compare/v0.1.0...HEAD
