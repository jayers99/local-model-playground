"""End-to-end smoke test for lmp.

Gated behind RUN_LIVE=1 because it loads a real local MLX model — far too
heavy for default test runs. Invoke with:

    RUN_LIVE=1 uv run pytest -v
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

LIVE = os.environ.get("RUN_LIVE") == "1"
EXAMPLE = Path("examples/terraform/service-account-bad-editor.tf")
OUTPUTS = Path("outputs")


@pytest.mark.skipif(not LIVE, reason="set RUN_LIVE=1 to run; needs a local MLX model")
def test_review_end_to_end() -> None:
    before = {p.name for p in OUTPUTS.glob("*-review.md")}

    result = subprocess.run(
        ["uv", "run", "lmp", "review", "--profile", "heavy", str(EXAMPLE)],
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert result.returncode == 0, (
        f"lmp review exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}\n"
    )

    after = {p.name for p in OUTPUTS.glob("*-review.md")}
    new_files = after - before
    assert len(new_files) == 1, f"Expected exactly one new review file, got: {new_files}"
    new_review = OUTPUTS / next(iter(new_files))

    text = new_review.read_text()
    for required_section in ("## Summary", "## Findings", "## Validation evidence", "## Open questions"):
        assert required_section in text, (
            f"Output missing required section: {required_section}\n\n--- file ---\n{text}"
        )

    findings_block = re.split(r"^## ", text, flags=re.MULTILINE)
    findings_section = next((b for b in findings_block if b.startswith("Findings")), "")
    assert "roles/editor" in findings_section, (
        f"Expected 'roles/editor' to appear in the Findings section. Got:\n{findings_section}"
    )


@pytest.mark.skipif(not LIVE, reason="set RUN_LIVE=1 to run; needs a local MLX model")
def test_chat_include_end_to_end() -> None:
    result = subprocess.run(
        [
            "uv", "run", "lmp", "chat",
            "--profile", "heavy",
            "--include", str(EXAMPLE),
        ],
        input="what's wrong with this?\nexit\n",
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert result.returncode == 0, (
        f"lmp chat exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}\n"
    )

    assert "roles/editor" in result.stdout.lower(), (
        "Expected the model's reply to mention 'roles/editor', proving the "
        "included file actually reached the model.\n"
        f"STDOUT:\n{result.stdout}"
    )
