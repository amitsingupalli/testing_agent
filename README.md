# testing-agent

**A self-testing layer for coding agents.** AI writes code fast — testing it hasn't kept up. `testing-agent` detects your project's stack, runs the right test suites (unit / integration / regression), gates the result, and writes a structured report your coding agent can read and act on, so it fixes its own work before you ever see a bug.

- **Zero-config** — stack auto-detection (Node, Python, Go, Rust), runner auto-selection
- **Gated runs** — exit codes agents can consume (`0` pass, `1` gate fail, `2` usage error)
- **Structured reports** — JSON + Markdown + rich terminal, written to `.testing-agent/`
- **Windows-first** — subprocess handling that actually works on Windows (no shell hacks)

> Status: **Phase 2** — everything in Phase 1 **plus test generation** (gap scanning,
> opencode/LLM backends, verify-and-retry loop) and **opencode integration**
> (plugin tools, tester subagent, skill). Security, performance, and compatibility
> runners are planned for Phases 3–4.

## Quickstart

```bash
# from the repo root
uv sync

# detect stacks (works in any project directory)
uv run testing-agent detect --path examples/node-demo

# run the unit suite and gate it
uv run testing-agent run --path examples/node-demo

# integration layer
uv run testing-agent run --path examples/node-demo --type integration

# regression baseline with git diff context
uv run testing-agent run --path examples/node-demo --type regression

# re-render the last report
uv run testing-agent report --path examples/node-demo
```

## How it works

```
detect  ──►  select runner  ──►  execute  ──►  parse (JUnit/JSON)  ──►  gate  ──►  report
```

1. **Detect** — scans the target (root + one level deep for monorepos) for
   `package.json`, `pyproject.toml`/`requirements*.txt`, `go.mod`, `Cargo.toml`
   and infers the stack, package manager, and test runner.
2. **Select** — picks an adapter: `pytest`, `vitest`, `jest`, or Node's built-in
   `node --test`. Stacks without an adapter yet (Go, Rust) are reported, not failed.
3. **Execute** — runs the suite with a machine-readable reporter
   (JUnit XML for pytest/vitest/node, aggregate JSON for jest), with a timeout and
   full stdout/stderr captured to `.testing-agent/logs/`.
4. **Gate** — a policy engine checks every required layer: suite passed, pass rate
   ≥ threshold, runner present (configurable warn vs fail).
5. **Report** — writes `last-report.json`, `last-report.md`, and a rich terminal
   summary including per-test failure details your agent can read.

### Test layers in Phase 1+2

| Layer    | What runs |
| -------- | --------- |
| unit     | `tests/` (pytest) or `tests/`+`tests/unit/` (Node) |
| integration | `tests/integration/` (pytest, Node) — scoped run |
| regression | baseline re-run of the unit suite + **git diff context** (changed files, test-vs-source) recorded in the report; diff-aware *selection* lands in Phase 3 |

## Test generation (Phase 2)

```bash
uv run testing-agent generate --path examples/python-demo            # auto backend
uv run testing-agent generate --path examples/python-demo -b manifest # no LLM: write gap manifest
```

How it works:

1. **Gap scan** — AST/regex scan finds public functions/classes/exports that are
   never referenced in any test file (Python + Node; Go/Rust coming).
2. **Backend** — `auto` picks the first available:
   `opencode` CLI → `ANTHROPIC_API_KEY` → `OPENAI_API_KEY` → gap manifest.
   Override with `--backend opencode|anthropic|openai|manifest`.
3. **Generate → verify → retry** — the backend writes `*_generated.*` test files
   (never touching hand-written tests), the suite re-runs, and failures are fed
   back for up to 2 more rounds.
4. **Reports** — `.testing-agent/last-generation.json` + `last-generation.md`,
   plus `gap-manifest.md` in manifest mode.

## opencode integration (Phase 2)

Ship-with-your-agent files live in [`opencode/`](opencode/):

| File | Purpose |
| --- | --- |
| `plugin.ts` | opencode plugin: `testing_agent_run` / `testing_agent_detect` tools + background gate after file edits |
| `agent/tester.md` | `tester` subagent: generates/fixes tests until the gate passes |
| `skill/testing-agent/SKILL.md` | Teaches any agent when/how to run the loop |

**Install into a project:** copy `plugin.ts` to `<project>/.opencode/plugins/testing-agent.ts`
and the agent/skill files into `<project>/.opencode/agent/` and `.opencode/skill/`.
Set `TESTING_AGENT_CMD="uvx testing-agent"` (or rely on the default `uvx` resolution)
so the plugin can call the CLI. Restart opencode after installing.

This repo dogfoods the integration: see `.opencode/`.

## Configuration

`uv run testing-agent init` writes a `.testing-agent.json` you can edit:

```json
{
  "root": ".",
  "timeout_seconds": 300,
  "gate": {
    "require_types": ["unit"],
    "min_pass_rate": 1.0,
    "fail_on_missing_runner": false,
    "fail_on_no_tests": false
  },
  "runner_overrides": {}
}
```

## Roadmap

- **Phase 1 (done)** — detection, unit/integration/regression runners, gate, reports
- **Phase 2 (done)** — LLM test generation (opencode delegation + direct API + gap manifest), opencode plugin/subagent/skill, git-diff regression context
- **Phase 3** — security (`npm audit`/`pip-audit`/semgrep), performance (k6/autocannon), system smoke runs, diff-aware test selection, JUnit CI output
- **Phase 4** — compatibility (Playwright browser matrix), GitHub Action, PyPI publish

## Development

```bash
uv sync              # install deps (dev group included)
uv run pytest        # run the tool's own test suite
```

## License

[MIT](LICENSE) — © 2026 Amit Singupalli
