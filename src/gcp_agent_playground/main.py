"""gcp-agent CLI entry point."""
from __future__ import annotations

from pathlib import Path

import typer

from . import profiles, workflows
from .llm_client import LLMClient
from .server import MLXServer, ServerError

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _run(profile_name: str, body) -> None:
    try:
        profile = profiles.load(profile_name)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)

    try:
        with MLXServer(profile):
            client = LLMClient(profile)
            body(client)
    except ServerError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=3)


@app.command()
def chat(profile: str = typer.Option("heavy", "--profile", "-p")) -> None:
    """Interactive chat with the local model."""
    _run(profile, lambda client: workflows.chat(client))


@app.command()
def review(
    input: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    profile: str = typer.Option("heavy", "--profile", "-p"),
) -> None:
    """Review a file and write a Markdown advisory to outputs/."""
    def _go(client: LLMClient) -> None:
        out_path = workflows.review(client, input)
        typer.echo(f"\nWrote: {out_path}")
    _run(profile, _go)


if __name__ == "__main__":
    app()
