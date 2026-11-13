---
name: testing-agent
description: Use when the user wants to test a project, verify AI-written code, run unit/integration/regression suites, or make the agent self-check its changes with testing-agent. Trigger words - testing-agent, run tests, test this project, gate, self-test.
---

# testing-agent

`testing-agent` is a self-testing layer: it detects the project's stack, runs the right
test runner, gates the result, and writes machine-readable reports. Use it after you
write or modify code so failures get fixed before the user ever sees them.

## Commands (shell)

```bash
testing-agent detect --path <dir>                 # stacks, package managers, runners
testing-agent run --path <dir>                    # unit suite + gate (exit 0/1)
testing-agent run --path <dir> --type integration # integration layer
testing-agent run --path <dir> --type regression  # baseline + git diff context
testing-agent generate --path <dir>               # generate tests for uncovered symbols
testing-agent report --path <dir> --markdown      # last report as markdown
```

If `testing-agent` is not on PATH, run it from its repo checkout with
`uv run --directory <testing-agent-repo> testing-agent ...`, or `uvx testing-agent`.

## The loop (do this after every code change)

1. Run the gate: `testing-agent run --path <dir>` (or use the `testing_agent_run` tool if available).
2. Exit code 0 → done. Exit 1 → read `.testing-agent/last-report.md` for the failing tests.
3. Fix the failing test OR the source bug (whichever is actually wrong), then re-run.
4. If the report says NO TESTS or MISSING RUNNER, surface that to the user — it's a finding.

## Generation

`testing-agent generate` scans for symbols with no test references and:

- `--backend auto` (default): uses opencode CLI if installed, then ANTHROPIC_API_KEY,
  then OPENAI_API_KEY, then writes a gap manifest.
- Manifest mode writes `.testing-agent/gap-manifest.md` — read it and write the tests yourself.

Generated tests always land in `*_generated.*` files. Never edit hand-written test files
to make the gate pass; fix real problems instead.

## Report locations

- `.testing-agent/last-report.json` / `.md` — test results + gate verdict
- `.testing-agent/last-generation.json` — generation outcomes
- `.testing-agent/logs/` — raw runner output for debugging
