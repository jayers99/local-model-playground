# `chat --include <path>` — Design Spec

**Date:** 2026-05-05
**Source:** `docs/backlog.md` → Feature backlog → priority:high
**Scope:** A single new flag on the existing `gcp-agent chat` command. No changes to `review`, profiles, server lifecycle, or prompt templates.

## 1. Purpose

Today the only way to get a file in front of the model in `chat` is to paste it into the REPL prompt. That goes haywire for anything beyond a few lines (terminal/input-buffer issues, plus uncertainty about what actually landed). `--include <path>` lets the user point `chat` at a file on disk; the harness reads it and folds it into the first user message before the REPL hands control over.

This closes the "I tried to paste a file and it went haywire" gap recorded in v1 lessons-learned.

## 2. Decisions locked during brainstorming

| Decision | Choice |
| --- | --- |
| Number of files | One. `--include` takes a single `Path`. |
| User feedback | Local echo line at REPL start: `Loaded <path> (<size>) — included with your first message.` |
| Size guardrail | Soft warning when file > 64 KB. No hard cap. |
| Approach | Buffer the file at REPL start, fold into the first user message when the user types. Do not auto-send a kickoff turn. |
| Path display | Show the path *as the user typed it* (relative or absolute, unresolved) inside delimiters so the model sees what the user sees. |
| Re-prepending | First user message only. Subsequent turns are normal; the file is in `history`. |

## 3. CLI shape

```
gcp-agent chat [--profile P] [--include PATH | -i PATH]
```

- `--include` / `-i`: optional `Path`. Default `None`.
- Typer validation: `exists=True, dir_okay=False, readable=True` — same as `review`'s input argument.
- Behavior with the flag absent is unchanged from v1.

### Example session

```
$ gcp-agent chat --profile heavy --include examples/terraform/service-account-bad-editor.tf
gcp-agent chat — Ctrl-D or 'exit' to quit
Loaded examples/terraform/service-account-bad-editor.tf (412 B) — included with your first message.

you> what's wrong with this?
agent> ...streams reply that has seen the file...
you> any narrower role you'd suggest?
agent> ...turn 2; file is in history but not re-prepended...
```

## 4. Wire format

When the user submits their first turn, the message body sent to the model is:

```
--- BEGIN INCLUDED FILE: <path-as-given> ---
<file content verbatim>
--- END INCLUDED FILE: <path-as-given> ---

<user's typed text>
```

The existing `_prepend_system` helper still merges the system prompt onto the front of this same first user message (Gemma's chat template doesn't accept a system role; this v1 quirk is unchanged). So the on-wire content of turn 1 is:

```
<system prompt>

--- BEGIN INCLUDED FILE: <path-as-given> ---
<file content>
--- END INCLUDED FILE: <path-as-given> ---

<user's typed text>
```

## 5. Module changes

### 5.1 `src/local_model_playground/workflows.py`

- New module constant: `INCLUDE_SIZE_WARN_BYTES = 64 * 1024`.
- New pure helper:

  ```python
  def _build_first_user_message(user_text: str, include_path: Path | None,
                                include_body: str | None) -> str
  ```

  - If `include_path is None` (and therefore `include_body is None`): return `user_text` unchanged.
  - Otherwise return the wire format from §4. The path used inside the delimiters is `str(include_path)` (i.e., as the user typed it on the CLI).
  - Pure function. No I/O. The body is passed in so the caller controls when the file is read and any read errors surface there, not buried inside this helper.

- `chat()` gains one parameter:

  ```python
  def chat(client: LLMClient, include_path: Path | None = None) -> None
  ```

- New behavior inside `chat()`, in order:
  1. Initialize local `include_body: str | None = None`.
  2. If `include_path is not None`:
     - Read the file via `include_path.read_text()`. On `UnicodeDecodeError`, print to stderr `Could not read <path> as UTF-8 text. Includes must be text files.` and call `sys.exit(2)`. (`workflows.py` already imports `sys`. We do not import `typer` here — keep workflows decoupled from the CLI framework.)
     - Compute `size = include_path.stat().st_size`.
     - Print local echo to stdout: `Loaded <path-as-given> (<human-readable size>) — included with your first message.`
     - If `size > INCLUDE_SIZE_WARN_BYTES`, print warning to stdout: `Warning: <path-as-given> is <human-readable size> — large includes may exceed the model's context window.`
     - Assign the file content to `include_body`.
  3. Print existing REPL banner.
  4. Enter REPL loop. Track a local `first_turn: bool = True`.
     - On each user turn, compute `user_msg = _build_first_user_message(user, include_path, include_body) if first_turn else user`.
     - After appending the assistant's reply to history, set `first_turn = False`.
     - Note: the helper itself returns `user_text` unchanged when `include_path is None`, so the `if first_turn` branch is safe to take whether or not an include was supplied — but the explicit `first_turn` flag makes the "first turn only" intent obvious in the code.

- Helper for size formatting: a small inline function `_human_size(n: int) -> str`:
  - `n < 1024` → `"<n> B"` (no decimals; e.g. `412 B`).
  - `1024 ≤ n < 1024*1024` → `"<n/1024:.1f> KB"` (one decimal; e.g. `64.0 KB`, `128.4 KB`).
  - `n ≥ 1024*1024` → `"<n/1024/1024:.1f> MB"` (one decimal; e.g. `2.3 MB`).
  - Lives in `workflows.py`; not worth a new module.

### 5.2 `src/local_model_playground/main.py`

- `chat` command gains:

  ```python
  include: Path | None = typer.Option(
      None, "--include", "-i",
      exists=True, dir_okay=False, readable=True,
      help="Path to a text file to include in the first user message.",
  )
  ```

- The lambda passed to `_run` becomes `lambda client: workflows.chat(client, include_path=include)`.

- No change to `review`. No change to `_run`.

## 6. Error handling

| Failure | Where | Behavior |
| --- | --- | --- |
| `--include` path doesn't exist | typer's `exists=True` | Standard typer error → exit 2; server never starts |
| `--include` path is a directory | typer's `dir_okay=False` | Standard typer error → exit 2 |
| `--include` path unreadable | typer's `readable=True` | Standard typer error → exit 2 |
| File is not UTF-8 | `read_text()` `UnicodeDecodeError` | Caught in `workflows.chat`; stderr message + `sys.exit(2)`; REPL never starts |
| File is empty (0 B) | n/a | Allowed. Echo shows `(0 B)`. Delimiters emitted with empty body. |
| File > 64 KB | size check | Warning line printed; proceeds |
| All other failures | unchanged | Existing `ServerError`, `KeyboardInterrupt`, etc., paths apply |

The file read and the size check happen *before* the REPL banner and *before* any model interaction, so a bad include never spins up a model session or leaves a half-printed banner.

## 7. Testing

### 7.1 Unit tests (`tests/test_workflows.py`, new file, no model required)

- `test_build_first_user_message_no_include` — `include_path=None, include_body=None` returns `user_text` unchanged.
- `test_build_first_user_message_with_include` — given a known body, returned string contains `--- BEGIN INCLUDED FILE: <path> ---`, body, `--- END INCLUDED FILE: <path> ---`, blank line, then `user_text`, in that order.
- `test_build_first_user_message_preserves_path_string` — relative paths stay relative; absolute stay absolute.

### 7.2 CLI wiring test (`tests/test_cli.py`, new file or extend existing)

- `test_chat_include_missing_file` — typer `CliRunner` invokes `chat --include /definitely/not/here.tf`; assert non-zero exit; assert no profile load was attempted (e.g., by patching `profiles.load` and asserting it was not called).

### 7.3 Live integration (`tests/test_smoke.py`, gated by `RUN_LIVE=1`)

- One new case: run `gcp-agent chat --profile heavy --include examples/terraform/service-account-bad-editor.tf` in a subprocess, pipe `"what's wrong with this?\nexit\n"` to stdin, assert exit 0 and that stdout contains `roles/editor` (case-insensitive).

### 7.4 Manual checklist (added to `notes/lessons-learned.md`)

- One bullet: include the bad-editor `.tf`, ask "what's wrong here?", confirm the model identifies `roles/editor` (proves the file content actually reached the model).

## 8. Definition of done

- `chat --include <path>` works end-to-end against the heavy profile.
- Local echo + size warning behave as specified.
- Bad-include cases (missing, directory, unreadable, non-UTF-8) fail before the server starts.
- Unit tests, CLI wiring test, and one live integration case all pass (live test gated).
- Manual checklist entry added to `notes/lessons-learned.md`.
- Backlog item is checked off in `docs/backlog.md`.

## 9. Out of scope

- Multiple `--include` flags. (Backlog records "single path" — multi-include can come back as a follow-on if it's actually wanted.)
- Including a directory or a glob.
- Re-prepending the file on later turns. (The file is in `history`; the model has it.)
- Any analogous flag on `review`. `review` already takes a file as its main argument; there's no gap to close.
- Token-aware truncation. The 64 KB warning is byte-based on purpose — token-aware logic is a separate (deferred) concern.
