"""testing-agent: a self-testing layer for coding agents."""

from __future__ import annotations


def main() -> None:
    """Entry point for the testing-agent CLI."""
    from testing_agent.cli import app

    app()


__all__ = ["main"]
