"""Command-line interface for testing-agent."""

from __future__ import annotations

from pathlib import Path

import typer

from testing_agent.config import ProjectConfig, load_config, save_config

app = typer.Typer(
    help="Self-testing layer for coding agents: detect the stack, run suites, gate changes.",
    no_args_is_help=True,
)


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project directory to analyze."),
) -> None:
    """Analyze a project and write a .testing-agent.json config."""
    root = path.resolve()
    if not root.is_dir():
        typer.secho(f"error: {root} is not a directory", fg="red", err=True)
        raise typer.Exit(code=2)

    existing = load_config(root)
    config = existing or ProjectConfig(root=str(root))
    if existing is None:
        config.root = str(root)
    file_path = save_config(root, config)

    typer.secho(f"Configuration written to {file_path}", fg="green")
    if existing is not None:
        typer.echo("Existing config loaded and re-saved (edit the file to customize).")


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
