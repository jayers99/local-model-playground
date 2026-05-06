"""High-level workflows: chat REPL and one-shot review."""
from __future__ import annotations

import sys
from pathlib import Path

from . import render
from .llm_client import LLMClient

PROMPTS_DIR = Path("prompts")


def _system_prompt() -> str:
    return (PROMPTS_DIR / "system.md").read_text()


def chat(client: LLMClient) -> None:
    """Interactive REPL. Read a user line, stream the assistant reply, repeat.

    'exit' or Ctrl-D to quit.
    """
    history: list[dict] = [{"role": "system", "content": _system_prompt()}]
    print("gcp-agent chat — Ctrl-D or 'exit' to quit\n")
    while True:
        try:
            user = input("you> ").strip()
        except EOFError:
            print()
            return
        if user.lower() in {"exit", "quit"} or not user:
            return
        history.append({"role": "user", "content": user})
        print("agent> ", end="", flush=True)
        chunks: list[str] = []
        for chunk in client.stream_chat(history):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            chunks.append(chunk)
        print()
        history.append({"role": "assistant", "content": "".join(chunks)})


def review(client: LLMClient, input_path: Path) -> Path:
    """One-shot review of a file. Returns the path to the written review.md."""
    template = (PROMPTS_DIR / "terraform_reviewer.md").read_text()
    user_msg = template.format(input_text=input_path.read_text())
    chunks: list[str] = []
    for chunk in client.stream_chat([
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": user_msg},
    ]):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        chunks.append(chunk)
    print()
    return render.write_review_md(
        body="".join(chunks),
        source=input_path,
        profile=client.profile,
    )
