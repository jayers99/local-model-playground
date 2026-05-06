# `chat --include <path>` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--include <path>` flag to `gcp-agent chat` that reads a text file once at REPL start and folds it (with a clear delimiter) into the user's first turn.

**Architecture:** Three new pure helpers in `workflows.py` — `_build_first_user_message`, `_human_size`, `_load_include_or_exit` — wired through an updated `chat()` and a new typer Option in `main.py`. The CLI framework (`typer`) handles existence/readability validation; only UTF-8 decoding is checked in `workflows.py`. No changes to the server, profiles, or `review`.

**Tech Stack:** Python 3.11+, `typer`, `pytest`, plus `typer.testing.CliRunner` for CLI wiring tests.

**Source spec:** `docs/superpowers/specs/2026-05-05-chat-include-design.md`

**Working assumptions for the executor:**
- Working directory is the repo root (`/Users/jayers/code/local-model-playground`).
- `uv sync` has already been run (so `pytest` is available via `uv run pytest`).
- Commits go to `main` directly (continuing the v1 convention).
- Each task ends with one commit. Use brief single-line commit messages focused on *why*.
- Run unit tests via `uv run pytest tests/test_workflows.py -v` (etc.). The live smoke test stays gated behind `RUN_LIVE=1`.

---

### Task 1: Pure helper `_build_first_user_message` — TDD

The first delivered increment: a pure function that returns the user's typed message verbatim when no include is supplied, and the wrapped wire format when an include is supplied. No I/O. Easy to test exhaustively.

**Files:**
- Create: `tests/test_workflows.py`
- Modify: `src/gcp_agent_playground/workflows.py` (add helper + import `Path` if not already present)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workflows.py` with this exact content (we will append to this file in later tasks; start with the tests for the first helper only):

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: `ImportError` or `AttributeError` — `_build_first_user_message` does not exist yet. All three tests fail at import time.

- [ ] **Step 3: Implement the helper**

Open `src/gcp_agent_playground/workflows.py`. Add `from pathlib import Path` if not already imported (it is). After the existing `_prepend_system` function (around line 27), add:

```python
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
    assert include_body is not None
    return (
        f"--- BEGIN INCLUDED FILE: {include_path} ---\n"
        f"{include_body}\n"
        f"--- END INCLUDED FILE: {include_path} ---\n"
        f"\n"
        f"{user_text}"
    )
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: 3 passed.

If `test_build_first_user_message_with_include` fails on a whitespace mismatch, double-check the exact placement of `\n` vs `\n\n` in the f-string — the body has its own trailing `\n`, then the helper adds another, giving the visible blank line before the END marker.

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflows.py src/gcp_agent_playground/workflows.py
git commit -m "feat(chat): add _build_first_user_message helper"
```

---

### Task 2: Pure helper `_human_size` — TDD

A formatter for the local echo line. Pinned to the format in spec §5.1: `412 B`, `64.0 KB`, `2.3 MB`.

**Files:**
- Modify: `tests/test_workflows.py` (append)
- Modify: `src/gcp_agent_playground/workflows.py` (append helper)

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_workflows.py` (under the existing tests, same module-level imports):

First, update the import line at the top from:

```python
from gcp_agent_playground.workflows import _build_first_user_message
```

to:

```python
from gcp_agent_playground.workflows import _build_first_user_message, _human_size
```

Then append at the bottom of the file:

```python
def test_human_size_bytes() -> None:
    assert _human_size(0) == "0 B"
    assert _human_size(412) == "412 B"
    assert _human_size(1023) == "1023 B"


def test_human_size_kilobytes() -> None:
    assert _human_size(1024) == "1.0 KB"
    assert _human_size(64 * 1024) == "64.0 KB"
    assert _human_size(int(128.4 * 1024)) == "128.4 KB"


def test_human_size_megabytes() -> None:
    assert _human_size(1024 * 1024) == "1.0 MB"
    assert _human_size(int(2.3 * 1024 * 1024)) == "2.3 MB"
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: import fails with `ImportError: cannot import name '_human_size'`. All tests fail at collection.

- [ ] **Step 3: Implement the helper**

Append to `src/gcp_agent_playground/workflows.py` after `_build_first_user_message`:

```python
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
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: 6 passed (3 from Task 1 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflows.py src/gcp_agent_playground/workflows.py
git commit -m "feat(chat): add _human_size formatter for include echo"
```

---

### Task 3: Helper `_load_include_or_exit` — file read, echo, warn, decode-error exit

This helper does the only I/O on the include path: read the text, print the local echo, optionally print the size warning, and `sys.exit(2)` on `UnicodeDecodeError`. Path-existence/readability checks already happen in typer (Task 5) — this helper does *not* re-validate them.

**Files:**
- Modify: `tests/test_workflows.py` (append tests)
- Modify: `src/gcp_agent_playground/workflows.py` (add `INCLUDE_SIZE_WARN_BYTES` constant + helper)

- [ ] **Step 1: Append the failing tests**

Update the import at the top of `tests/test_workflows.py` to:

```python
import pytest

from gcp_agent_playground.workflows import (
    INCLUDE_SIZE_WARN_BYTES,
    _build_first_user_message,
    _human_size,
    _load_include_or_exit,
)
```

Append at the bottom of `tests/test_workflows.py`:

```python
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: import fails — `INCLUDE_SIZE_WARN_BYTES` and `_load_include_or_exit` don't exist yet.

- [ ] **Step 3: Implement the constant and helper**

In `src/gcp_agent_playground/workflows.py`, near the top (after existing imports, before `PROMPTS_DIR`), add:

```python
INCLUDE_SIZE_WARN_BYTES = 64 * 1024
```

Then append after `_human_size`:

```python
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
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `uv run pytest tests/test_workflows.py -v`

Expected: 10 passed.

If `test_load_include_exits_on_non_utf8` fails because `read_text()` didn't raise, the file's bytes happened to be decodable on this system. Use a more reliably-bad sequence — `b"\xff\xfe\xfd"` typically suffices. (The test as written should be fine; this is a fallback note.)

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflows.py src/gcp_agent_playground/workflows.py
git commit -m "feat(chat): add _load_include_or_exit with size warn + decode-error exit"
```

---

### Task 4: Wire the helpers into `chat()` and add the `--include` CLI option

Now hook the helpers into the REPL and surface the flag in typer. Also add a CLI wiring test that confirms typer's existence check fires *before* the profile is loaded.

**Files:**
- Modify: `src/gcp_agent_playground/workflows.py` (replace `chat()` body)
- Modify: `src/gcp_agent_playground/main.py` (add `--include` Option, update lambda)
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI wiring tests**

Create `tests/test_cli.py`:

```python
"""CLI wiring tests (no model required)."""
from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from gcp_agent_playground.main import app


def test_chat_help_includes_include_flag() -> None:
    """The --help output proves --include is a recognized option."""
    runner = CliRunner()
    result = runner.invoke(app, ["chat", "--help"])
    assert result.exit_code == 0, result.output
    assert "--include" in result.output
    assert "-i" in result.output


def test_chat_include_missing_file_fails_before_profile_load() -> None:
    """A bad --include path must be rejected by typer's exists=True
    *before* profiles.load runs (so we never spin a server on a bad include).
    """
    runner = CliRunner()
    with patch("gcp_agent_playground.profiles.load") as mock_load:
        result = runner.invoke(
            app,
            ["chat", "--include", "/definitely/not/here.tf", "--profile", "heavy"],
        )
    assert result.exit_code != 0
    mock_load.assert_not_called()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/test_cli.py -v`

Expected:
- `test_chat_help_includes_include_flag` — FAIL. The help output for `chat` does not yet contain `--include`, so the assertion fires. This is the primary deterministic-fail signal that drives this task's TDD cycle.
- `test_chat_include_missing_file_fails_before_profile_load` — may pass accidentally (typer rejects the unknown option `--include`, exit code is non-zero, and `profiles.load` was never called). That accidental pass becomes a real assertion after the flag is wired in Step 4. Don't worry if it passes here.

- [ ] **Step 3: Update `chat()` in `workflows.py`**

Open `src/gcp_agent_playground/workflows.py`. Replace the existing `chat()` function (the one currently around lines 29–52) with:

```python
def chat(client: LLMClient, include_path: Path | None = None) -> None:
    """Interactive REPL. Read a user line, stream the assistant reply, repeat.

    'exit' or Ctrl-D to quit. If include_path is given, the file's content is
    folded into the first user message with a clear delimiter.
    """
    include_body = _load_include_or_exit(include_path)
    history: list[dict] = []
    print("gcp-agent chat — Ctrl-D or 'exit' to quit\n")
    first_turn = True
    while True:
        try:
            user = input("you> ").strip()
        except EOFError:
            print()
            return
        if user.lower() in {"exit", "quit"} or not user:
            return
        user_msg = (
            _build_first_user_message(user, include_path, include_body)
            if first_turn
            else user
        )
        history.append({"role": "user", "content": user_msg})
        print("agent> ", end="", flush=True)
        chunks: list[str] = []
        for chunk in client.stream_chat(_prepend_system(history)):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            chunks.append(chunk)
        print()
        history.append({"role": "assistant", "content": "".join(chunks)})
        first_turn = False
```

- [ ] **Step 4: Update `main.py` to surface `--include`**

Open `src/gcp_agent_playground/main.py`. Replace the current `chat` command (around lines 32–35):

```python
@app.command()
def chat(profile: str = typer.Option("heavy", "--profile", "-p")) -> None:
    """Interactive chat with the local model."""
    _run(profile, lambda client: workflows.chat(client))
```

with:

```python
@app.command()
def chat(
    profile: str = typer.Option("heavy", "--profile", "-p"),
    include: Path | None = typer.Option(
        None,
        "--include",
        "-i",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to a text file to include in the first user message.",
    ),
) -> None:
    """Interactive chat with the local model."""
    _run(profile, lambda client: workflows.chat(client, include_path=include))
```

- [ ] **Step 5: Run the full test suite and confirm everything passes**

Run: `uv run pytest tests/test_workflows.py tests/test_cli.py -v`

Expected: 12 passed (10 workflows tests + 2 CLI wiring tests).

If `test_chat_help_includes_include_flag` still fails after Step 4, the option isn't being registered — re-check that the `include: Path | None = typer.Option(...)` line is present in `main.chat`'s signature.

If `test_chat_include_missing_file_fails_before_profile_load`'s `mock_load.assert_not_called()` fails, typer is letting the command body run before validating `--include`. Re-check that `exists=True, dir_okay=False, readable=True` are all on the `Option` call.

- [ ] **Step 6: Sanity-check the help output**

Run: `uv run gcp-agent chat --help`

Expected: Help output shows `--include / -i PATH` with the help text. No errors. (`--help` does not enter the REPL.)

(A full live `chat` test against the model is part of Task 5, gated by `RUN_LIVE=1`.)

- [ ] **Step 7: Commit**

```bash
git add tests/test_cli.py src/gcp_agent_playground/workflows.py src/gcp_agent_playground/main.py
git commit -m "feat(chat): wire --include path through chat REPL"
```

---

### Task 5: Live integration test (gated)

Add one gated end-to-end case to `tests/test_smoke.py` that runs the real chat with `--include` against the heavy profile and asserts the model's response acknowledged the file content (by mentioning `roles/editor`).

**Files:**
- Modify: `tests/test_smoke.py` (append a second test function)

- [ ] **Step 1: Append the new gated test**

Append to `tests/test_smoke.py`:

```python
@pytest.mark.skipif(not LIVE, reason="set RUN_LIVE=1 to run; needs a local MLX model")
def test_chat_include_end_to_end() -> None:
    result = subprocess.run(
        [
            "uv", "run", "gcp-agent", "chat",
            "--profile", "heavy",
            "--include", str(EXAMPLE),
        ],
        input="what's wrong with this?\nexit\n",
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert result.returncode == 0, (
        f"gcp-agent chat exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}\n"
    )

    assert "roles/editor" in result.stdout.lower(), (
        "Expected the model's reply to mention 'roles/editor', proving the "
        "included file actually reached the model.\n"
        f"STDOUT:\n{result.stdout}"
    )
```

- [ ] **Step 2: Confirm the test is collected but skipped (default run)**

Run: `uv run pytest tests/test_smoke.py -v`

Expected: 2 tests, both skipped (`SKIPPED` due to `RUN_LIVE != "1"`). No failures.

- [ ] **Step 3: Run the test live**

Run: `RUN_LIVE=1 uv run pytest tests/test_smoke.py::test_chat_include_end_to_end -v`

Expected: PASSED. (May take 1–3 minutes on the heavy profile; the model has to spin up and produce a reply.)

If it fails on `"roles/editor" in result.stdout.lower()`, inspect `result.stdout` — the model may have referred to it as "the editor role" or similar. If the model's content-mention is clearly there but doesn't hit that exact string, broaden the assertion (e.g., check for `"editor"` and `"role"` separately) and document the change in the commit message.

If `returncode != 0`, the most likely causes are: heavy profile not configured (`profiles/heavy.yaml` missing the model slug), `mlx_lm.server` failing to bind, or the model not pulled. Address those separately — they're not include-feature bugs.

- [ ] **Step 4: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test(chat): add gated end-to-end smoke test for --include"
```

---

### Task 6: Documentation cleanup — backlog tickoff + lessons-learned bullet

Mark the feature done in the backlog and add a one-line entry to the manual checklist in `notes/lessons-learned.md` so the next live-walk includes the new flag.

**Files:**
- Modify: `docs/backlog.md`
- Modify: `notes/lessons-learned.md`

- [ ] **Step 1: Check off the backlog item**

In `docs/backlog.md`, find the line:

```
- [ ] **`chat --include <path>`** flag. Read a file, prepend it (with a clear delimiter) to the first user message of the REPL session. Closes the "I tried to paste a file and it went haywire" gap directly.
```

Change `- [ ]` to `- [x]`.

- [ ] **Step 2: Add a manual-checklist bullet to `notes/lessons-learned.md`**

If `notes/lessons-learned.md` does not yet have a manual-checklist section, look for the v1 manual checklist (it should exist per the v1 plan); if it does not exist either, add a new section header `## Manual checklist (post-v1 features)` at the bottom of the file before adding the bullet.

Append to the manual checklist (or create the section first):

```markdown
- [ ] `chat --include`: run `gcp-agent chat --profile heavy --include examples/terraform/service-account-bad-editor.tf`, ask "what's wrong here?", confirm the model identifies `roles/editor` (proves the file content reached the model). Note any size-warning behavior for follow-up calibration.
```

- [ ] **Step 3: Confirm the file changes look right**

Run: `git diff docs/backlog.md notes/lessons-learned.md`

Expected: backlog item flipped to `[x]`; one new bullet appended in lessons-learned.

- [ ] **Step 4: Commit**

```bash
git add docs/backlog.md notes/lessons-learned.md
git commit -m "docs: tick off chat --include + add manual checklist note"
```

---

## Definition of done (for the executor)

After all six tasks land, the spec's §8 should hold:

- `chat --include <path>` works end-to-end against the heavy profile (verified by Task 5 with `RUN_LIVE=1`).
- Local echo and size warning behave per spec (verified by Tasks 2 & 3 unit tests).
- Bad-include cases fail before the server starts (Task 3 covers UTF-8; Task 4's CLI test covers missing path; existence/dir/readable are typer's own).
- Unit, CLI wiring, and gated live tests all pass.
- Manual checklist bullet exists in `notes/lessons-learned.md`.
- Backlog item is checked off in `docs/backlog.md`.
