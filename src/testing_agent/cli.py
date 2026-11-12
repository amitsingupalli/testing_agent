"""Command-line interface for testing-agent."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    help="Self-testing layer for coding agents: detect the stack, run suites, gate changes.",
    no_args_is_help=True,
)


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to analyze."),
) -> None:
    """Analyze a project and write a .testing-agent.json config."""
    typer.echo(f"init: analyzing {path} (wired up in an upcoming commit)")


@app.command()
def detect(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to analyze."),
) -> None:
    """Detect stacks and test runners used by the project."""
    typer.echo(f"detect: analyzing {path} (wired up in an upcoming commit)")


@app.command()
def run(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to test."),
    test_type: str = typer.Option(
        "unit", "--type", "-t", help="Test type: unit, integration, or regression."
    ),
) -> None:
    """Run the applicable test suites and gate the result."""
    typer.echo(f"run: {test_type} in {path} (wired up in an upcoming commit)")


@app.command()
def report(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory."),
) -> None:
    """Render the last test report."""
    typer.echo(f"report: {path} (wired up in an upcoming commit)")


@app.command()
def generate(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory."),
) -> None:
    """Generate tests for uncovered code (Phase 2)."""
    typer.echo("Test generation lands in Phase 2 of the roadmap.")


if __name__ == "__main__":
    app()
