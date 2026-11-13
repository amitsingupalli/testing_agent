"""Command-line interface for testing-agent."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer
from rich.console import Console

from testing_agent.config import ProjectConfig, load_config, save_config
from testing_agent.detect import detect_project
from testing_agent.gate import evaluate
from testing_agent.report import GateSummary, build_report
from testing_agent.report.json_report import load_json_report, write_json_report
from testing_agent.report.markdown_report import render_markdown, write_markdown_report
from testing_agent.report.terminal import print_terminal
from testing_agent.runners import select_runner
from testing_agent.runners.base import RunResult, TestType

app = typer.Typer(
    help="Self-testing layer for coding agents: detect the stack, run suites, gate changes.",
    no_args_is_help=True,
)
console = Console()


class TestTypeChoice(str, Enum):
    unit = "unit"
    integration = "integration"
    regression = "regression"


def _resolve_root(path: Path) -> Path:
    root = path.resolve()
    if not root.is_dir():
        typer.secho(f"error: {root} is not a directory", fg="red", err=True)
        raise typer.Exit(code=2)
    return root


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to analyze."),
) -> None:
    """Analyze a project and write a .testing-agent.json config."""
    root = _resolve_root(path)
    detection = detect_project(root)

    existing = load_config(root)
    config = existing or ProjectConfig(root=str(root))
    if existing is None:
        config.root = str(root)
    file_path = save_config(root, config)

    console.print(f"[green]Configuration written to {file_path}[/green]")
    if detection.manifests:
        console.print(f"Detected {len(detection.manifests)} project(s) — run [bold]detect[/bold] for details.")
    else:
        console.print("[yellow]No known stacks detected here yet.[/yellow]")


@app.command()
def detect(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to analyze."),
    as_json: bool = typer.Option(False, "--json", help="Print raw JSON instead of a table."),
) -> None:
    """Detect stacks and test runners used by the project."""
    root = _resolve_root(path)
    detection = detect_project(root)

    if as_json:
        console.print_json(detection.model_dump_json())
        return

    from rich.table import Table

    table = Table(title=f"Detected projects in {root}")
    for column in ("Directory", "Stack", "Package manager", "Name", "Test runner"):
        table.add_column(column)
    for manifest in detection.manifests:
        table.add_row(
            manifest.directory or ".",
            manifest.stack.value,
            manifest.package_manager.value,
            manifest.name or "—",
            manifest.test_runner or "—",
        )
    console.print(table)
    if detection.is_monorepo:
        console.print("[bold]Monorepo detected[/bold] — every manifest above gets its own run.")
    if not detection.manifests:
        console.print("[yellow]No known stacks detected.[/yellow]")


@app.command()
def run(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to test."),
    test_type: TestTypeChoice = typer.Option(
        TestTypeChoice.unit, "--type", "-t", help="Test layer to run."
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the report JSON to stdout."),
) -> None:
    """Run the applicable test suites, gate the result, and write a report."""
    root = _resolve_root(path)
    chosen = TestType(test_type.value)

    detection = detect_project(root)
    config = load_config(root) or ProjectConfig(root=str(root))

    results: list[RunResult] = []
    for manifest in detection.manifests:
        runner = select_runner(manifest, chosen)
        if runner is None:
            results.append(
                RunResult(
                    runner="none",
                    test_type=chosen,
                    manifest_directory=manifest.directory,
                    missing_runner=True,
                    note=(
                        f"no adapter yet for stack '{manifest.stack.value}' "
                        f"(runner '{manifest.test_runner}') — planned in a later phase"
                    ),
                )
            )
            continue
        results.append(runner.run(manifest, root, chosen, config.timeout_seconds))

    extra: dict | None = None
    if chosen == TestType.REGRESSION:
        from testing_agent.git_context import collect_git_context

        context = collect_git_context(root)
        summary = context.summary()
        for result in results:
            result.note = f"{result.note} | {summary}" if result.note else summary
        extra = {
            "regression_context": {
                "is_repo": context.is_repo,
                "changed_files": context.changed_files,
                "has_test_changes": context.has_test_changes,
                "has_source_changes": context.has_source_changes,
                "mode": "baseline (diff-aware selection lands in Phase 3)",
            }
        }

    gate_result = evaluate(results, config.gate, chosen)
    gate_summary = GateSummary(
        passed=gate_result.passed,
        checks=[check.model_dump() for check in gate_result.checks],
    )
    report = build_report(str(root), results, gate_summary, extra=extra)
    json_path = write_json_report(root, report)
    write_markdown_report(root, report)

    if as_json:
        console.print_json(_report_json(report))
    else:
        print_terminal(report, console)
        console.print(f"\n[dim]Reports written: {json_path} (+ last-report.md)[/dim]")

    raise typer.Exit(code=0 if gate_result.passed else 1)


def _report_json(report: dict) -> str:
    import json as _json

    return _json.dumps(report, indent=2)


@app.command()
def report(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory."),
    as_markdown: bool = typer.Option(False, "--markdown", "-m", help="Print markdown output."),
) -> None:
    """Render the last test report."""
    root = _resolve_root(path)
    data = load_json_report(root)
    if data is None:
        typer.secho(
            "No report found — run `testing-agent run` first.", fg="yellow", err=True
        )
        raise typer.Exit(code=2)

    if as_markdown:
        typer.echo(render_markdown(data))
    else:
        print_terminal(data, console)


@app.command()
def generate(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory."),
    backend: str = typer.Option(
        "auto", "--backend", "-b", help="Generation backend: auto, opencode, anthropic, openai, manifest."
    ),
    max_files: int = typer.Option(3, "--max-files", help="Maximum source files to cover."),
    as_json: bool = typer.Option(False, "--json", help="Print the generation report JSON."),
) -> None:
    """Generate tests for code without test coverage, then verify they pass."""
    root = _resolve_root(path)
    from testing_agent.generate.backends import GenerationError
    from testing_agent.generate.generator import generate_tests, write_generation_report
    from testing_agent.generate.models import GenerationReport

    try:
        report = generate_tests(
            root,
            backend_id=backend,
            max_files=max_files,
            timeout_seconds=300,
            feedback_rounds=2,
        )
    except GenerationError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=2) from error

    write_generation_report(root, report)

    from testing_agent.report.generation_report import write_generation_markdown

    write_generation_markdown(root, report)

    if as_json:
        console.print_json(report.model_dump_json())
    else:
        from rich.table import Table

        table = Table(title=f"Generation ({report.backend} backend)")
        for column in ("Source file", "Test file", "Rounds", "Status", "Note"):
            table.add_column(column)
        for outcome in report.outcomes:
            status = "PASS" if outcome.success else "FAIL"
            style = "green" if outcome.success else "red"
            table.add_row(
                outcome.source_file,
                outcome.test_file or "—",
                str(outcome.rounds),
                f"[{style}]{status}[/{style}]",
                (outcome.note or outcome.error or "")[:60],
            )
        console.print(table)
        if report.manifest_path:
            console.print(f"[yellow]Gap manifest: {report.manifest_path}[/yellow]")

    raise typer.Exit(code=0 if report.all_success else 1)


if __name__ == "__main__":
    app()
