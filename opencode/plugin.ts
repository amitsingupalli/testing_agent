/**
 * testing-agent plugin for opencode (V1 plugin API).
 *
 * Adds:
 * - `testing_agent_run` tool: run the gate and return verdict + failures
 * - `testing_agent_detect` tool: detect stacks/runners for a directory
 * - an event hook that runs the gate in the background after file edits
 *
 * Command resolution: TESTING_AGENT_CMD env var (space-separated), then
 * `uvx testing-agent`, then `uv run testing-agent`.
 */
import { type Plugin, tool } from "@opencode-ai/plugin"
import { execFile } from "node:child_process"
import { promises as fs } from "node:fs"
import * as path from "node:path"

interface PluginOptions {
  command?: string[]
}

const RUN_TIMEOUT_MS = 600_000
const EDIT_DEBOUNCE_MS = 4_000
const MAX_MESSAGE_CHARS = 6_000

function resolveCommand(options?: PluginOptions): string[] {
  const fromEnv = process.env.TESTING_AGENT_CMD
  if (fromEnv && fromEnv.trim()) {
    return fromEnv.trim().split(/\s+/)
  }
  if (options?.command && options.command.length > 0) {
    return options.command
  }
  return ["uvx", "testing-agent"]
}

function exec(
  command: string[],
  args: string[],
  cwd: string,
  timeoutMs: number,
): Promise<{ stdout: string; stderr: string; exitCode: number | null; failed: boolean }> {
  return new Promise((resolve) => {
    execFile(
      command[0],
      [...command.slice(1), ...args],
      { cwd, timeout: timeoutMs, windowsHide: true, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout, stderr) => {
        const failed = Boolean(error)
        resolve({
          stdout: typeof stdout === "string" ? stdout : "",
          stderr: typeof stderr === "string" ? stderr : "",
          exitCode: error && typeof (error as { code?: unknown }).code === "number" ? (error as { code: number }).code : null,
          failed,
        })
      },
    )
  })
}

async function readReport(root: string): Promise<string> {
  try {
    const raw = await fs.readFile(path.join(root, ".testing-agent", "last-report.json"), "utf8")
    const report = JSON.parse(raw) as {
      verdict?: string
      results?: Array<{
        runner?: string
        test_type?: string
        manifest_directory?: string
        passed?: number
        failed?: number
        errors?: number
        skipped?: number
        verdict?: string
        failures?: Array<{ name?: string; message?: string }>
      }>
      gate?: { checks?: Array<{ name?: string; passed?: boolean; detail?: string }> }
    }

    const lines: string[] = [`Verdict: ${report.verdict ?? "?"}`]
    for (const result of report.results ?? []) {
      lines.push(
        `- ${result.runner}/${result.test_type} (${result.manifest_directory || "."}): ` +
          `${result.passed ?? 0} passed, ${result.failed ?? 0} failed, ${result.errors ?? 0} errors — ${result.verdict ?? "?"}`,
      )
      for (const failure of result.failures ?? []) {
        const message = (failure.message ?? "no message").slice(0, 300)
        lines.push(`  FAIL ${failure.name ?? "?"}: ${message}`)
      }
    }
    for (const check of report.gate?.checks ?? []) {
      if (check.passed === false) {
        lines.push(`GATE FAIL ${check.name}: ${check.detail ?? ""}`)
      }
    }
    return lines.join("\n")
  } catch {
    return "(no report file found — the run may have failed before writing one)"
  }
}

function truncate(text: string, max = MAX_MESSAGE_CHARS): string {
  if (text.length <= max) return text
  return `${text.slice(0, max)}\n... (truncated)`
}

export function createTestingAgentPlugin(options?: PluginOptions): Plugin {
  const command = resolveCommand(options)
  let inflight = false
  let debounceTimer: ReturnType<typeof setTimeout> | undefined

  const runCli = async (args: string[], cwd: string, timeoutMs = RUN_TIMEOUT_MS) => {
    const result = await exec(command, args, cwd, timeoutMs)
    const output = (result.stdout || "") + (result.stderr ? `\n${result.stderr}` : "")
    return { ...result, output }
  }

  return (async (context) => {
    const directory = context.directory || process.cwd()

    const scheduleBackgroundRun = () => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(async () => {
        if (inflight) return
        inflight = true
        try {
          const result = await runCli(["run", "--path", directory], directory, 300_000)
          const reportText = await readReport(directory)
          const verdict = reportText.startsWith("Verdict: PASS")
          if (result.failed) {
            console.warn(`[testing-agent] background run failed: ${truncate(result.output, 400)}`)
          } else if (!verdict) {
            console.warn(`[testing-agent] gate FAILED after edit:\n${truncate(reportText, 1200)}`)
          } else {
            console.log("[testing-agent] gate passed after edit")
          }
        } catch (error) {
          console.warn(`[testing-agent] background run error: ${String(error)}`)
        } finally {
          inflight = false
        }
      }, EDIT_DEBOUNCE_MS)
    }

    return {
      event: async (evt: unknown) => {
        const event = (evt as { event?: { type?: string }; type?: string })?.event ??
          (evt as { type?: string }) ?? {}
        const type = String(event.type ?? "")
        const lower = type.toLowerCase()
        const isEdit =
          lower.includes("file") &&
          (lower.includes("edit") || lower.includes("write") || lower.includes("patch"))
        if (isEdit) {
          scheduleBackgroundRun()
        }
      },
      tool: {
        testing_agent_run: tool({
          description:
            "Run testing-agent test suites (unit by default; integration/regression via type) for a directory and return the gate verdict plus failing tests. Use this after writing or fixing code.",
          args: {
            path: tool.schema.string().optional().describe("Project directory (defaults to the current directory)"),
            type: tool.schema.string().optional().describe("Test layer: unit, integration, or regression"),
          },
          async execute(args, toolContext) {
            const root = path.resolve(toolContext.directory || directory, args.path || ".")
            const type = (args.type || "unit").toLowerCase()
            const result = await runCli(["run", "--path", root, "--type", type], root)
            const reportText = await readReport(root)
            if (result.failed) {
              return truncate(
                `testing-agent run failed to start (${command.join(" ")}). ${result.output.slice(0, 500)}\n${reportText}`,
              )
            }
            return truncate(reportText)
          },
        }),
        testing_agent_detect: tool({
          description:
            "Detect the stacks, package managers, and test runners testing-agent finds in a directory.",
          args: {
            path: tool.schema.string().optional().describe("Project directory (defaults to the current directory)"),
          },
          async execute(args, toolContext) {
            const root = path.resolve(toolContext.directory || directory, args.path || ".")
            const result = await runCli(["detect", "--path", root, "--json"], root, 60_000)
            if (result.failed) {
              return `detect failed: ${truncate(result.output, 400)}`
            }
            return truncate(result.stdout.trim() || "(no output)")
          },
        }),
      },
    }
  }) satisfies Plugin
}

export default createTestingAgentPlugin()
