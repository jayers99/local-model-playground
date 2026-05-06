# GCP Agent Playground v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the First Implementation Slice of `gcp-agent` — a local CLI that spawns `mlx_lm.server` on the heavy MacBook profile, exposes `chat` and `review` commands, and writes a Markdown advisory for one synthetic Terraform example.

**Architecture:** Python `typer` CLI wired to a flat-module package (`profiles`, `server`, `llm_client`, `workflows`, `render`). The CLI manages the `mlx_lm.server` subprocess per invocation and connects to it as an OpenAI-compatible HTTP endpoint via the `openai` SDK with token streaming.

**Tech Stack:** Python 3.11+, `uv`, `typer`, `pydantic`, `pyyaml`, `openai` SDK, `mlx-lm` (Apple MLX runtime).

**Source spec:** `docs/superpowers/specs/2026-05-05-gcp-agent-playground-design.md`

**Working assumptions for the executor:**
- Working directory is the root of the `gemma-play-1` repo.
- You are on the heavy MacBook profile (M5 Max, 128 GB).
- Commits go to `main` directly (this is a fresh POC repo; no feature branch needed unless the user requests one).
- Tests are smoke-only by design (per spec §1) — do **not** add per-module unit tests.
- Each task ends with a commit. Use brief single-line commit messages focused on *why*.

---

### Task 1: Discover the actual MLX model slug for the heavy profile

The brief's `mlx-community/gemma-4-31b-it-4bit` may not exist. We need a real slug before anything else, because every later task assumes a working model.

**Files:**
- Modify (later in this task): the value will be written into `profiles/heavy.yaml` in Task 3.

- [ ] **Step 1: Probe the brief's slug**

Run: `curl -sI https://huggingface.co/mlx-community/gemma-4-31b-it-4bit`

Expected: HTTP 200 → use this slug, skip to Step 4.
If 404 → continue to Step 2.

- [ ] **Step 2: List available Gemma models in `mlx-community`**

Open `https://huggingface.co/mlx-community?search_models=gemma` in a browser (or `curl` the page) and note candidates. We want a model that:
- Fits comfortably in 128 GB unified memory (so any 4-bit-quantized model up to ~70B params is safe).
- Is instruction-tuned (`-it` suffix).
- Is the newest Gemma family with a working 4-bit quant.

Realistic fallback candidates (in preference order):
1. `mlx-community/gemma-3-27b-it-4bit`
2. `mlx-community/gemma-3-12b-it-4bit`
3. `mlx-community/gemma-2-27b-it-4bit`

- [ ] **Step 3: Verify the chosen slug exists**

Run: `curl -sI https://huggingface.co/<chosen-slug>`

Expected: HTTP 200.

- [ ] **Step 4: Record the chosen slug**

Hold the slug in scratch/notes for Task 3. Example: `CHOSEN_MODEL=mlx-community/gemma-3-27b-it-4bit`

- [ ] **Step 5: No commit for this task**

This task produces a value, not a code change. Move to Task 2.

---

### Task 2: Scaffold the Python project

**Files:**
- Create: `pyproject.toml`
- Create: `src/gcp_agent_playground/__init__.py` (empty)
- Modify: `.gitignore` (append outputs rules)
- Create: `outputs/.gitkeep` (empty)
- Create: `outputs/.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "gcp-agent-playground"
version = "0.1.0"
description = "Local agentic AI playground for synthetic GCP/Terraform advisory tasks"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pydantic>=2.7",
    "pyyaml>=6",
    "openai>=1.40",
    "httpx>=0.27",
    "mlx-lm>=0.18",
]

[project.scripts]
gcp-agent = "gcp_agent_playground.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/gcp_agent_playground"]

[dependency-groups]
dev = [
    "pytest>=8",
]
```

- [ ] **Step 2: Create the package init**

Create `src/gcp_agent_playground/__init__.py` with empty content.

- [ ] **Step 3: Append outputs rules to `.gitignore`**

Append (use Edit tool, do not rewrite the whole file):

```
# gcp-agent runtime artifacts
outputs/*
!outputs/.gitkeep
!outputs/.gitignore
```

- [ ] **Step 4: Create the outputs directory placeholders**

Create `outputs/.gitkeep` (empty).

Create `outputs/.gitignore` with:

```
*
!.gitignore
!.gitkeep
```

(This belt-and-braces ensures generated files inside `outputs/` are never committed even if the top-level `.gitignore` is ever changed.)

- [ ] **Step 5: Install and verify**

Run: `uv sync`

Expected: creates `.venv`, installs deps, exits 0.

Run: `uv run gcp-agent --help`

Expected: This will FAIL because `main:app` doesn't exist yet. The error should mention `ModuleNotFoundError: gcp_agent_playground.main` — that's expected. We just want to confirm `uv sync` worked and the entry point is wired.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/gcp_agent_playground/__init__.py .gitignore outputs/.gitkeep outputs/.gitignore
git commit -m "chore: scaffold gcp-agent-playground Python project"
```

---

### Task 3: Profile loading

**Files:**
- Create: `src/gcp_agent_playground/profiles.py`
- Create: `profiles/heavy.yaml`
- Create: `profiles/light.yaml`

- [ ] **Step 1: Write `profiles.py`**

Create `src/gcp_agent_playground/profiles.py`:

```python
"""Profile loading for the gcp-agent CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str
    description: str
    runtime: Literal["mlx"]
    model: str
    host: str = "127.0.0.1"
    port: int = 8080
    base_url: str
    temperature: float = 0.3
    max_tokens: int = 4000
    intended_use: list[str] = Field(default_factory=list)


def load(name: str, profiles_dir: Path = Path("profiles")) -> Profile:
    path = profiles_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{name}' not found at {path}"
        )
    data = yaml.safe_load(path.read_text())
    return Profile.model_validate(data)
```

- [ ] **Step 2: Write `profiles/heavy.yaml`**

Use the slug chosen in Task 1. Replace `<CHOSEN_MODEL>` below.

```yaml
name: heavy
description: "128 GB MacBook profile for deeper local synthesis"
runtime: mlx
model: <CHOSEN_MODEL>
host: 127.0.0.1
port: 8080
base_url: http://127.0.0.1:8080/v1
temperature: 0.3
max_tokens: 4000
intended_use:
  - larger Terraform review
  - deeper GCP reasoning
```

- [ ] **Step 3: Write `profiles/light.yaml`**

The light profile is written for schema parity but is not exercised in v1. Leave the model slug as a placeholder.

```yaml
name: light
description: "36 GB MacBook profile for fast local experiments (not exercised in v1)"
runtime: mlx
model: TODO-discover-light-slug
host: 127.0.0.1
port: 8080
base_url: http://127.0.0.1:8080/v1
temperature: 0.3
max_tokens: 2000
intended_use:
  - concept explanation
  - small Terraform review
```

- [ ] **Step 4: Sanity-check the loader**

Run a one-liner to confirm parsing:

```bash
uv run python -c "from gcp_agent_playground.profiles import load; p = load('heavy'); print(p.model, p.base_url)"
```

Expected: prints the chosen model slug and `http://127.0.0.1:8080/v1`.

- [ ] **Step 5: Commit**

```bash
git add src/gcp_agent_playground/profiles.py profiles/heavy.yaml profiles/light.yaml
git commit -m "feat: profile loader with pydantic schema and heavy/light yaml"
```

---

### Task 4: MLX server lifecycle wrapper

This is the most subprocess-heavy module. It owns starting `mlx_lm.server`, polling readiness, and guaranteed cleanup.

**Files:**
- Create: `src/gcp_agent_playground/server.py`

- [ ] **Step 1: Write `server.py`**

Create `src/gcp_agent_playground/server.py`:

```python
"""Lifecycle wrapper for a local mlx_lm.server subprocess."""
from __future__ import annotations

import atexit
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .profiles import Profile

LOG_DIR = Path("outputs/.server-logs")
READY_POLL_INTERVAL_S = 0.5
LOG_TAIL_LINES = 20


class ServerError(RuntimeError):
    """Raised when the local model server fails to start or stop cleanly."""


class MLXServer:
    def __init__(self, profile: Profile):
        self.profile = profile
        self._proc: subprocess.Popen | None = None
        self._log_path: Path | None = None
        self._stopped = False

    # ---- public API -----------------------------------------------------

    def start(self, ready_timeout_s: float = 120.0) -> None:
        if self._already_serving():
            raise ServerError(
                f"Port {self.profile.port} is already serving a model. "
                f"Stop the existing server or change the port in your profile."
            )

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        self._log_path = LOG_DIR / f"{ts}.log"
        log_file = self._log_path.open("w")

        try:
            self._proc = subprocess.Popen(
                [
                    "mlx_lm.server",
                    "--model", self.profile.model,
                    "--host", self.profile.host,
                    "--port", str(self.profile.port),
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        except FileNotFoundError as e:
            raise ServerError(
                "mlx_lm.server not found on PATH. Did you 'uv sync'? "
                "Try: uv run mlx_lm.server --help"
            ) from e

        atexit.register(self.stop)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._wait_ready(ready_timeout_s)

    def stop(self, term_grace_s: float = 5.0) -> None:
        if self._stopped or self._proc is None:
            return
        self._stopped = True
        proc = self._proc
        if proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=term_grace_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except ProcessLookupError:
            pass

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.profile.base_url}/models", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    # ---- context manager -----------------------------------------------

    def __enter__(self) -> "MLXServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ---- internals -----------------------------------------------------

    def _already_serving(self) -> bool:
        return self.is_ready()

    def _wait_ready(self, timeout_s: float) -> None:
        assert self._proc is not None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self._raise_with_log_tail(
                    f"mlx_lm.server exited with code {self._proc.returncode} before becoming ready."
                )
            if self.is_ready():
                return
            time.sleep(READY_POLL_INTERVAL_S)
        self.stop()
        self._raise_with_log_tail(
            f"mlx_lm.server did not become ready within {timeout_s:.0f}s."
        )

    def _raise_with_log_tail(self, message: str) -> None:
        tail = ""
        if self._log_path and self._log_path.exists():
            lines = self._log_path.read_text().splitlines()[-LOG_TAIL_LINES:]
            tail = "\n".join(lines)
        raise ServerError(f"{message}\n\n--- last {LOG_TAIL_LINES} lines of {self._log_path} ---\n{tail}")

    def _signal_handler(self, signum, frame) -> None:
        self.stop()
        # Re-raise the default behavior so the process actually exits.
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
```

- [ ] **Step 2: Sanity-check by importing**

Run: `uv run python -c "from gcp_agent_playground.server import MLXServer; print('ok')"`

Expected: prints `ok` (no syntax/import errors).

We are deferring the live start/stop test to the end-to-end smoke test in Task 11.

- [ ] **Step 3: Commit**

```bash
git add src/gcp_agent_playground/server.py
git commit -m "feat: subprocess lifecycle for local mlx_lm.server"
```

---

### Task 5: LLM client

**Files:**
- Create: `src/gcp_agent_playground/llm_client.py`

- [ ] **Step 1: Write `llm_client.py`**

Create `src/gcp_agent_playground/llm_client.py`:

```python
"""Thin OpenAI-SDK wrapper pointed at the local mlx_lm.server."""
from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI

from .profiles import Profile


class LLMClient:
    def __init__(self, profile: Profile):
        self.profile = profile
        self._client = OpenAI(base_url=profile.base_url, api_key="not-needed")

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.profile.model,
            messages=messages,
            temperature=self.profile.temperature,
            max_tokens=self.profile.max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content
```

- [ ] **Step 2: Sanity-check by importing**

Run: `uv run python -c "from gcp_agent_playground.llm_client import LLMClient; print('ok')"`

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/gcp_agent_playground/llm_client.py
git commit -m "feat: openai-sdk wrapper for local mlx server with token streaming"
```

---

### Task 6: Prompts and the synthetic Terraform example

**Files:**
- Create: `prompts/system.md`
- Create: `prompts/terraform_reviewer.md`
- Create: `examples/terraform/service-account-bad-editor.tf`

- [ ] **Step 1: Write `prompts/system.md`**

```markdown
You are a local AI assistant for learning GCP infrastructure engineering, Terraform, cloud security, and agentic AI harness design.

This is a proof-of-concept playground. Use fake examples only. Provide practical engineering advice, identify assumptions, explain risks, and suggest validation steps.

Do not claim something is production-ready. Distinguish explanation, recommendation, and evidence. Prefer clear, structured output.
```

- [ ] **Step 2: Write `prompts/terraform_reviewer.md`**

The template uses `{input_text}` as the substitution slot. Note the use of literal triple-backticks in the template — this is intentional: the rendered prompt will contain a fenced code block.

```markdown
You are reviewing a Terraform snippet for a GCP infrastructure engineer.
The snippet is fake/educational — do not claim production compliance.

Review the snippet below and produce a Markdown report with these sections:

## Summary
One paragraph: what the snippet does, in plain language.

## Findings
For each issue you identify, write a bullet with:
- **Issue:** what the problem is
- **Why it matters:** the engineering / security risk
- **Suggested change:** a narrower, safer alternative
- **Confidence:** high / medium / low

## Validation evidence
What an engineer should inspect or run to confirm the deployed state matches the intent.

## Open questions
What you can't determine from the snippet alone.

---

Terraform snippet:

` ` `hcl
{input_text}
` ` `
```

(In the actual file, the three backtick-space sequences must be three plain backticks — I've spaced them in this plan to avoid escaping issues. Write the file with real triple-backticks around `{input_text}`.)

- [ ] **Step 3: Write `examples/terraform/service-account-bad-editor.tf`**

```hcl
# Synthetic example. Not real infrastructure. Demonstrates an overly-broad IAM role.

resource "google_service_account" "deploy" {
  account_id   = "app-deploy"
  display_name = "App deployment service account"
}

resource "google_project_iam_member" "deploy_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}
```

- [ ] **Step 4: Verify the prompt template substitution works**

Run:

```bash
uv run python -c "
from pathlib import Path
template = Path('prompts/terraform_reviewer.md').read_text()
example = Path('examples/terraform/service-account-bad-editor.tf').read_text()
rendered = template.format(input_text=example)
print(rendered[:500])
print('---')
print(rendered[-200:])
"
```

Expected: prints the start and end of the rendered prompt; the Terraform code appears inside the fenced block at the bottom; no `KeyError` from `.format`.

- [ ] **Step 5: Commit**

```bash
git add prompts/system.md prompts/terraform_reviewer.md examples/terraform/service-account-bad-editor.tf
git commit -m "feat: system + terraform-reviewer prompts and one synthetic example"
```

---

### Task 7: Workflows

**Files:**
- Create: `src/gcp_agent_playground/workflows.py`

- [ ] **Step 1: Write `workflows.py`**

Create `src/gcp_agent_playground/workflows.py`:

```python
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
```

- [ ] **Step 2: Sanity-check by importing**

Run: `uv run python -c "from gcp_agent_playground.workflows import chat, review; print('ok')"`

Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/gcp_agent_playground/workflows.py
git commit -m "feat: chat REPL and one-shot review workflows"
```

---

### Task 8: Output rendering

**Files:**
- Create: `src/gcp_agent_playground/render.py`

- [ ] **Step 1: Write `render.py`**

Create `src/gcp_agent_playground/render.py`:

```python
"""Markdown output rendering for review workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .profiles import Profile

OUTPUTS_DIR = Path("outputs")


def write_review_md(*, body: str, source: Path, profile: Profile,
                    out_dir: Path = OUTPUTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = out_dir / f"{ts}-review.md"
    header = (
        f"<!--\n"
        f"source: {source}\n"
        f"profile: {profile.name}\n"
        f"model: {profile.model}\n"
        f"timestamp: {ts}\n"
        f"-->\n\n"
    )
    out_path.write_text(header + body)
    return out_path
```

- [ ] **Step 2: Sanity-check write**

Run:

```bash
uv run python -c "
from pathlib import Path
from gcp_agent_playground.render import write_review_md
from gcp_agent_playground.profiles import load
p = write_review_md(body='# test\n\nbody\n', source=Path('examples/terraform/service-account-bad-editor.tf'), profile=load('heavy'))
print('wrote', p)
print(p.read_text()[:300])
"
```

Expected: prints `wrote outputs/<timestamp>-review.md` and shows the header + body.

Then clean up the test artifact:

```bash
rm outputs/*-review.md
```

- [ ] **Step 3: Commit**

```bash
git add src/gcp_agent_playground/render.py
git commit -m "feat: write_review_md emits timestamped markdown with metadata header"
```

---

### Task 9: CLI wiring

**Files:**
- Create: `src/gcp_agent_playground/main.py`

- [ ] **Step 1: Write `main.py`**

Create `src/gcp_agent_playground/main.py`:

```python
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
```

- [ ] **Step 2: Verify CLI surface**

Run: `uv run gcp-agent --help`

Expected: typer help output listing `chat` and `review` commands.

Run: `uv run gcp-agent review --help`

Expected: help text showing `INPUT` argument and `--profile/-p` option.

- [ ] **Step 3: Verify error path with bad profile name**

Run: `uv run gcp-agent chat --profile nope`

Expected: prints `Profile 'nope' not found at profiles/nope.yaml` to stderr and exits non-zero (code 2).

- [ ] **Step 4: Commit**

```bash
git add src/gcp_agent_playground/main.py
git commit -m "feat: typer CLI wires chat and review through profile + server lifecycle"
```

---

### Task 10: Notes and README

**Files:**
- Create: `notes/future-hardening.md`
- Create: `notes/lessons-learned.md`
- Modify: `README.md`

- [ ] **Step 1: Write `notes/future-hardening.md`**

```markdown
# Future hardening

Items deliberately deferred from v1. Listed here so they aren't lost.

## Deferred from v1 scope

- `compare` command (run light + heavy profiles against the same input)
- Static Terraform checks (regex/keyword-based detection of `roles/editor`, `roles/owner`, `roles/viewer`, service-account-key resources)
- JSON output artifact (`review.json`) and a structured-output schema
- `gcp_tutor` prompt template + GCP concept-tutor workflow
- `acceptance_to_validation` prompt template + ticket-decomposition workflow
- `examples/tickets/` synthetic acceptance-criteria examples
- Light-profile end-to-end exercise + the lessons-learned comparison table
- Daemon-mode server lifecycle (currently per-invocation; revisit if cold-start UX hurts)

## Deferred hardening (from the original brief)

- Redaction and secret scanning
- Corporate data-handling rules
- Local log retention policy
- Prompt/output audit trail
- Policy-as-code integration
- Terraform `plan` JSON parsing
- Read-only GCP validation commands
- Approval workflow
- Threat model
- Enterprise packaging
- Internal model approval process
- Concurrent-invocation lock files / PID files
- Crashed-server recovery
- Retry on transient HTTP errors
- Model-output safety / redaction
```

- [ ] **Step 2: Write `notes/lessons-learned.md`**

```markdown
# Lessons learned

This file is filled in as v1 is exercised. After walking the manual smoke checklist (see `docs/superpowers/specs/2026-05-05-gcp-agent-playground-design.md` §7.2), record:

- Surprises during install or first run
- Cold-start time observed for the heavy profile
- Quality observations on the synthetic Terraform review
- Any flag/CLI shape changes in `mlx_lm.server` we had to work around
- Tasks the local model handled well vs. tasks where it underperformed
```

- [ ] **Step 3: Rewrite `README.md`**

```markdown
# gcp-agent-playground

Local agentic AI playground for synthetic GCP/Terraform advisory tasks. Runs a local MLX-hosted Gemma model on Apple Silicon and exposes a small `gcp-agent` CLI for `chat` and `review` workflows.

This is a learning POC. Use fake/educational inputs only — see `docs/idea.md` for the full brief and non-goals.

## Quickstart (heavy profile, M5 Max 128 GB)

1. Install Python deps:

       uv sync

2. Pre-pull the MLX model declared in `profiles/heavy.yaml`:

       uv run huggingface-cli download <model-slug-from-heavy.yaml>

3. Chat:

       uv run gcp-agent chat --profile heavy

4. Review the bundled example:

       uv run gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf

   The advisory Markdown lands in `outputs/<timestamp>-review.md`.

## Layout

- `docs/idea.md` — the original POC brief
- `docs/superpowers/specs/` — design spec
- `docs/superpowers/plans/` — implementation plan
- `profiles/` — per-machine MLX runtime profiles
- `prompts/` — system + workflow prompt templates
- `examples/` — synthetic inputs
- `src/gcp_agent_playground/` — the CLI implementation
- `outputs/` — generated reviews (gitignored)
- `notes/future-hardening.md` — deferred work
- `notes/lessons-learned.md` — observations

## What's not here yet

See `notes/future-hardening.md`. Notably: no `compare` command, no static checks, no JSON output, no light-profile validation in v1.
```

- [ ] **Step 4: Commit**

```bash
git add notes/future-hardening.md notes/lessons-learned.md README.md
git commit -m "docs: future-hardening, lessons-learned scaffolding, quickstart README"
```

---

### Task 11: Smoke test

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write `tests/__init__.py`**

Create empty `tests/__init__.py`.

- [ ] **Step 2: Write `tests/test_smoke.py`**

Create `tests/test_smoke.py`:

```python
"""End-to-end smoke test for gcp-agent.

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
        ["uv", "run", "gcp-agent", "review", "--profile", "heavy", str(EXAMPLE)],
        capture_output=True,
        text=True,
        timeout=600,
    )

    assert result.returncode == 0, (
        f"gcp-agent review exited {result.returncode}\n"
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
```

- [ ] **Step 3: Verify the test is collected and skipped without `RUN_LIVE`**

Run: `uv run pytest tests/test_smoke.py -v`

Expected: 1 skipped, 0 failed.

- [ ] **Step 4: Commit (test infrastructure only — RUN_LIVE happens in Task 12)**

```bash
git add tests/__init__.py tests/test_smoke.py
git commit -m "test: gated end-to-end smoke for gcp-agent review"
```

---

### Task 12: Live smoke + manual checklist walk

This task exercises the system end-to-end on real hardware and records observations. It produces no code commit; only a notes commit.

**Files:**
- Modify: `notes/lessons-learned.md`

- [ ] **Step 1: Pull the model (if not already cached)**

Run: `uv run huggingface-cli download <model-slug-from-heavy.yaml>`

Expected: model cached in `~/.cache/huggingface/`. May take several minutes on first download.

- [ ] **Step 2: Run the gated smoke test**

Run: `RUN_LIVE=1 uv run pytest tests/test_smoke.py -v`

Expected: 1 passed. Cold-start may take 30 s – 2 min for the model to load before the request streams. If it exceeds `MLXServer`'s 120-second readiness timeout, increase `ready_timeout_s` (passed to `start()` from `MLXServer.__enter__`) — record the observed time in lessons-learned.

- [ ] **Step 3: Walk the manual checklist (spec §7.2)**

For each item, record observation in `notes/lessons-learned.md`:

1. `uv run gcp-agent --help` lists `chat` and `review`.
2. Server `/v1/models` responds within ~30 s (note actual time observed).
3. `uv run gcp-agent chat --profile heavy` — ask: *"Explain workload identity federation in two paragraphs."* Tokens stream; response is coherent.
4. `uv run gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf` — finds `roles/editor` is overly broad, recommends a narrower role, includes Validation Evidence and Open Questions.
5. During a long review, hit Ctrl-C. Then run `pgrep -f mlx_lm.server` — expect no output (server cleaned up).
6. Run `review` twice in a row. Confirm two distinct timestamped files exist in `outputs/`.
7. (Optional) Edit `profiles/light.yaml` to point at any small Gemma model and run `gcp-agent chat --profile light` for a quick sanity check that profile swapping works. Revert any non-final edit afterward.

- [ ] **Step 4: Commit lessons-learned updates**

```bash
git add notes/lessons-learned.md
git commit -m "docs: capture v1 smoke + manual checklist observations"
```

- [ ] **Step 5: v1 done**

At this point all spec §7.3 acceptance criteria are met:

- All Section 5 spec files exist with the content specified.
- `gcp-agent chat` and `gcp-agent review` both run end-to-end on the heavy machine.
- The smoke test passes with `RUN_LIVE=1`.
- The manual checklist has been walked and observations are in `notes/lessons-learned.md`.
- `notes/future-hardening.md` lists every deferred item.
- `README.md` quickstart matches reality.
- Design + plan are committed under `docs/superpowers/specs/` and `docs/superpowers/plans/`.

---

## Self-review (executed before saving this plan)

**Spec coverage:** Each spec section maps to tasks:
- Spec §1 (scope decisions) → fixed in plan working assumptions and tasks 2–9.
- Spec §2 (architecture) → realised in tasks 4, 5, 7, 9.
- Spec §3 (repo layout) → realised in tasks 2, 3, 6, 7, 8, 9, 10.
- Spec §4 (modules) → tasks 3 (profiles), 4 (server), 5 (llm_client), 7 (workflows), 8 (render), 9 (main).
- Spec §5 (file content) → tasks 3, 6, 8, 10.
- Spec §6 (error handling) → covered by `MLXServer.ServerError`, the pre-spawn port probe, the typer-level exit codes in `main.py`, and the `FileNotFoundError` mapping.
- Spec §7 (verification) → tasks 11 (smoke test) and 12 (live walk + lessons-learned).
- Spec §8 (open risks) → risk #1 (model URI) handled by Task 1; risk #2 (startup time) surfaced via the configurable `ready_timeout_s`; risk #3 (mlx_lm version drift) addressed by pinning `mlx-lm>=0.18` in `pyproject.toml` and surfacing CLI errors via the log-tail mechanism.

**Placeholder scan:** No "TBD"/"TODO"/"implement later"/"add appropriate error handling" patterns. The only intentional placeholder is `<CHOSEN_MODEL>` in the heavy profile YAML, which Task 1 explicitly resolves before Task 3 writes the file.

**Type consistency:** `Profile`, `LLMClient`, `MLXServer`, `ServerError`, `write_review_md`, `chat`, `review`, `load` — names and signatures match across the tasks where they're defined and where they're consumed.
