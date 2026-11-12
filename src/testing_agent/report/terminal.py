"""Rich terminal renderer for reports."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table


def print_terminal(report: dict[str, Any], console: Console | None = None) -> None:
    """Render a report dict to the terminal with rich formatting."""
    console = console or Console()

    verdict = report.get("verdict", "UNKNOWN")
    style = "bold green" if verdict == "PASS" else "bold red"
    console.print(f"\n[bold]testing-agent[/bold] — target [cyan]{report.get('target', '?')}[/cyan]")
    console.print(f"Verdict: [{style}]{verdict}[/{style}]\n")

    results = report.get("results") or []
    if results:
        table = Table(title="Test results", show_lines=False)
        for column in ("Runner", "Type", "Project", "Pass", "Fail", "Err", "Skip", "Time", "Status"):
            table.add_column(column)
        for result in results:
            status = str(result.get("verdict", "?"))
            status_style = (
                "green" if status == "PASS" else "yellow" if status in ("NO TESTS", "MISSING RUNNER") else "red"
            )
            table.add_row(
                str(result.get("runner", "?")),
                str(result.get("test_type", "?")),
                result.get("manifest_directory") or ".",
                str(result.get("passed", 0)),
                str(result.get("failed", 0)),
                str(result.get("errors", 0)),
                str(result.get("skipped", 0)),
                f"{result.get('duration_ms', 0)} ms",
                f"[{status_style}]{status}[/{status_style}]",
            )
        console.print(table)
    else:
        console.print("[yellow]No test runners ran for this target.[/yellow]")

    gate = report.get("gate") or {}
    checks = gate.get("checks") or []
    if checks:
        gate_table = Table(title="Gate checks", show_lines=False)
        gate_table.add_column("Check")
        gate_table.add_column("Result")
        gate_table.add_column("Detail")
        for check in checks:
            passed = bool(check.get("passed"))
            gate_table.add_row(
                str(check.get("name", "?")),
                "[green]PASS[/green]" if passed else "[red]FAIL[/red]",
                str(check.get("detail", "")),
            )
        console.print(gate_table)

    failures = [
        (result, failure)
        for result in results
        for failure in (result.get("failures") or [])
    ]
    if failures:
        console.print("\n[bold red]Failures[/bold red]")
        for result, failure in failures:
            console.print(f"\n[bold]{result.get('runner')} — {failure.get('name', '?')}[/bold]")
            message = failure.get("message") or "no message"
            console.print(message)
