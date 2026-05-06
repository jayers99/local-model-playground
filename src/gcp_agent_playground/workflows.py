"""High-level workflows: chat REPL and one-shot review."""
from __future__ import annotations

import sys
from pathlib import Path

from . import render
from .llm_client import LLMClient

PROMPTS_DIR = Path("prompts")


def _system_prompt() -> str:
    return (PROMPTS_DIR / "system.md").read_text()


def _prepend_system(messages: list[dict]) -> list[dict]:
    # Gemma's chat template doesn't accept a system role, so mlx_lm.server
    # returns 404 {"error": "System role not supported"}. Merge the system
    # prompt into the first user message instead.
    out = list(messages)
    for i, m in enumerate(out):
        if m.get("role") == "user":
            out[i] = {"role": "user", "content": f"{_system_prompt()}\n\n{m['content']}"}
            break
    return out


def chat(client: LLMClient) -> None:
    """Interactive REPL. Read a user line, stream the assistant reply, repeat.

    'exit' or Ctrl-D to quit.
    """
    history: list[dict] = []
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
        for chunk in client.stream_chat(_prepend_system(history)):
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
    for chunk in client.stream_chat(_prepend_system([
        {"role": "user", "content": user_msg},
    ])):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        chunks.append(chunk)
    print()
    return render.write_review_md(
        body="".join(chunks),
        source=input_path,
        profile=client.profile,
    )
