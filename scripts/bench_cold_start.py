"""Measure cold-start phases for one profile.

Usage:
    uv run python scripts/bench_cold_start.py <profile>

Reports three durations (seconds, monotonic clock):
    listener_ready_s — process start → /v1/models returns 200 (HTTP listener up)
    first_token_s    — listener-ready → first streamed chunk arrives (model load + prefill)
    full_response_s  — listener-ready → end of response stream

The first-token phase dominates cold-start because the server lazy-loads the model
on the first chat completion request.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gcp_agent_playground import profiles
from gcp_agent_playground.llm_client import LLMClient
from gcp_agent_playground.server import MLXServer
from gcp_agent_playground.workflows import _prepend_system


def main(profile_name: str) -> None:
    t0 = time.monotonic()
    profile = profiles.load(profile_name)
    server = MLXServer(profile)
    first_token_at: float | None = None
    try:
        server.start(ready_timeout_s=600.0)
        t1 = time.monotonic()

        client = LLMClient(profile)
        messages = _prepend_system([
            {"role": "user", "content": "Say hello in one short sentence."}
        ])
        for _ in client.stream_chat(messages):
            if first_token_at is None:
                first_token_at = time.monotonic()
        t2 = time.monotonic()
    finally:
        server.stop()

    listener = t1 - t0
    first = (first_token_at - t1) if first_token_at is not None else float("nan")
    full = t2 - t1
    print(
        f"{profile_name}\t"
        f"listener_ready_s={listener:.1f}\t"
        f"first_token_s={first:.1f}\t"
        f"full_response_s={full:.1f}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bench_cold_start.py <profile>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
