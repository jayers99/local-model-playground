"""Unit tests for workflows helpers (no model required)."""
from __future__ import annotations

from pathlib import Path

from gcp_agent_playground.workflows import _build_first_user_message


def test_build_first_user_message_no_include() -> None:
    assert _build_first_user_message("hello", None, None) == "hello"


def test_build_first_user_message_with_include() -> None:
    out = _build_first_user_message(
        "what's wrong here?",
        Path("examples/foo.tf"),
        'resource "x" {}\n',
    )
    expected = (
        "--- BEGIN INCLUDED FILE: examples/foo.tf ---\n"
        'resource "x" {}\n'
        "\n"
        "--- END INCLUDED FILE: examples/foo.tf ---\n"
        "\n"
        "what's wrong here?"
    )
    assert out == expected


def test_build_first_user_message_preserves_path_string(tmp_path: Path) -> None:
    rel = Path("a/b.tf")
    abs_p = tmp_path / "x.tf"
    out_rel = _build_first_user_message("u", rel, "x")
    out_abs = _build_first_user_message("u", abs_p, "x")
    assert "BEGIN INCLUDED FILE: a/b.tf" in out_rel
    assert f"BEGIN INCLUDED FILE: {abs_p}" in out_abs
