/**
 * In-repo wiring for the testing-agent opencode plugin.
 *
 * opencode auto-discovers `.opencode/plugins/*.ts`. This file re-exports the
 * canonical plugin from `opencode/plugin.ts`, pinned to this repo's uv
 * environment (`uv run testing-agent`) so the CLI doesn't need to be installed.
 */
import { createTestingAgentPlugin } from "../../opencode/plugin"

export default createTestingAgentPlugin({ command: ["uv", "run", "testing-agent"] })
