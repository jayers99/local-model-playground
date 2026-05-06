"""Unit tests for workflows helpers (no model required)."""
from __future__ import annotations

from pathlib import Path

import pytest

from gcp_agent_playground.workflows import (
    INCLUDE_SIZE_WARN_BYTES,
    _build_first_user_message,
    _human_size,
    _load_include_or_exit,
)


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


def test_human_size_bytes() -> None:
    assert _human_size(0) == "0 B"
    assert _human_size(412) == "412 B"
    assert _human_size(1023) == "1023 B"


def test_human_size_kilobytes() -> None:
    assert _human_size(1024) == "1.0 KB"
    assert _human_size(64 * 1024) == "64.0 KB"
    assert _human_size(int(128.4 * 1024)) == "128.4 KB"
    assert _human_size(1024 * 1024 - 1) == "1024.0 KB"


def test_human_size_megabytes() -> None:
    assert _human_size(1024 * 1024) == "1.0 MB"
    assert _human_size(int(2.3 * 1024 * 1024)) == "2.3 MB"


def test_load_include_returns_none_when_path_is_none() -> None:
    assert _load_include_or_exit(None) is None


def test_load_include_reads_file_and_prints_echo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "small.tf"
    p.write_text('resource "x" {}\n')
    body = _load_include_or_exit(p)
    assert body == 'resource "x" {}\n'
    out = capsys.readouterr().out
    assert f"Loaded {p}" in out
    assert "included with your first message." in out
    assert "Warning:" not in out


def test_load_include_warns_on_large_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "big.tf"
    p.write_text("x" * (INCLUDE_SIZE_WARN_BYTES + 1))
    body = _load_include_or_exit(p)
    assert body is not None
    out = capsys.readouterr().out
    assert "Loaded" in out
    assert "Warning:" in out
    assert "may exceed the model's context window" in out


def test_load_include_exits_on_non_utf8(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\xff\xfe\x00\x01\x02\x03")
    with pytest.raises(SystemExit) as exc:
        _load_include_or_exit(p)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Could not read" in err
    assert "as UTF-8 text" in err


def test_chat_only_prepends_include_on_first_turn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The include is folded into turn 1's user message; turn 2 is bare user text."""
    from gcp_agent_playground import workflows

    monkeypatch.setattr(workflows, "_system_prompt", lambda: "SYS")

    include_file = tmp_path / "tiny.tf"
    include_file.write_text('resource "x" {}\n')

    inputs = iter(["first question", "second question", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    seen_messages: list[list[dict]] = []

    class FakeClient:
        profile = None

        def stream_chat(self, messages: list[dict]):
            seen_messages.append([dict(m) for m in messages])
            yield "ok"

    workflows.chat(FakeClient(), include_path=include_file)

    assert len(seen_messages) == 2

    turn1 = seen_messages[0]
    assert len(turn1) == 1
    assert "--- BEGIN INCLUDED FILE:" in turn1[0]["content"]
    assert "first question" in turn1[0]["content"]

    turn2 = seen_messages[1]
    assert turn2[-1]["role"] == "user"
    assert "--- BEGIN INCLUDED FILE:" not in turn2[-1]["content"]
    assert turn2[-1]["content"] == "second question"
