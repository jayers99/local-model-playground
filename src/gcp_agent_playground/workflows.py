"""High-level workflows: chat REPL and one-shot review."""
from __future__ import annotations

import sys
from pathlib import Path

from . import render
from .llm_client import LLMClient

INCLUDE_SIZE_WARN_BYTES = 64 * 1024

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


def _build_first_user_message(
    user_text: str,
    include_path: Path | None,
    include_body: str | None,
) -> str:
    """Wrap user_text with delimited include content if a file was included.

    No I/O — caller passes the already-read body. When include_path is None,
    returns user_text unchanged.
    """
    if include_path is None:
        return user_text
    if include_body is None:
        raise ValueError("include_body must be provided when include_path is set")
    return (
        f"--- BEGIN INCLUDED FILE: {include_path} ---\n"
        f"{include_body}\n"
        f"--- END INCLUDED FILE: {include_path} ---\n"
        f"\n"
        f"{user_text}"
    )


def _human_size(n: int) -> str:
    """Format a byte count as a short human-readable string.

    < 1 KiB  -> "<n> B"      (no decimals)
    < 1 MiB  -> "<n/1024:.1f> KB"
    >= 1 MiB -> "<n/1024**2:.1f> MB"
    """
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _load_include_or_exit(include_path: Path | None) -> str | None:
    """Read the include file, print the echo (and warning if large).

    Returns the file body, or None when no path was given.
    On UnicodeDecodeError: prints to stderr and sys.exit(2).
    """
    if include_path is None:
        return None
    try:
        body = include_path.read_text()
    except UnicodeDecodeError:
        print(
            f"Could not read {include_path} as UTF-8 text. "
            f"Includes must be text files.",
            file=sys.stderr,
        )
        sys.exit(2)
    size = include_path.stat().st_size
    print(
        f"Loaded {include_path} ({_human_size(size)}) — "
        f"included with your first message."
    )
    if size > INCLUDE_SIZE_WARN_BYTES:
        print(
            f"Warning: {include_path} is {_human_size(size)} — "
            f"large includes may exceed the model's context window."
        )
    return body


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
