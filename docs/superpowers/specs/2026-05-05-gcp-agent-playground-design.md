# GCP Agent Playground — v1 Design Spec

**Date:** 2026-05-05
**Source brief:** `docs/idea.md`
**Scope:** First Implementation Slice only (the brief's "after that works" items and the full vision are deferred to follow-on work captured in `notes/future-hardening.md`).

## 1. Purpose & scope decisions

The brief is a POC playground for local Apple-Silicon models advising on synthetic GCP/Terraform examples. This spec covers only the **First Implementation Slice**:

- Python CLI skeleton
- Profile YAML loading
- OpenAI-compatible local model client
- `chat` command (interactive REPL)
- `review` command (one-shot file review)
- One prompt template (Terraform reviewer)
- One synthetic Terraform example (overly-broad IAM)
- Markdown output written to `outputs/`

**Explicitly out of v1:** `compare` command, static Terraform checks, JSON output artifact, the `gcp_tutor` and `acceptance_to_validation` prompts, the `tickets/` examples, the lessons-learned/comparison tables, and any exercise of the light profile beyond schema parity.

### Decisions locked during brainstorming

| Decision                  | Choice                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| Dev hardware              | Heavy MacBook (M5 Max, 128 GB)                                                                  |
| Server lifecycle          | CLI manages it — `gcp-agent` spawns `mlx_lm.server` per invocation, waits for ready, stops on exit |
| Repo placement            | At the root of `local-model-playground/` (this repo *is* the project)                           |
| Tests                     | Smoke-only — one gated end-to-end test plus a manual checklist                                  |
| Model URI                 | Treat as TBD — v1 setup includes a "discover correct slug on `mlx-community`" step              |
| CLI framework             | `typer`                                                                                         |
| HTTP client               | Official `openai` SDK pointed at the local `base_url`                                           |
| Streaming                 | Yes — token-level streaming to stdout for both commands                                         |
| Profile validation        | `pydantic`                                                                                      |
| Module shape              | Flat modules per concern, functions over classes (except `MLXServer` which owns lifecycle state) |

## 2. Architecture & control flow

```
┌──────────────┐
│  user shell  │  $ gcp-agent review examples/terraform/sa-bad-editor.tf --profile heavy
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│ gcp-agent CLI (typer)                                                │
│                                                                      │
│  1. parse args → profile name + workflow + input                     │
│  2. profiles.load("heavy") → Profile (pydantic model)                │
│  3. server.start(profile) → spawn mlx_lm.server as subprocess        │
│       └─ poll http://127.0.0.1:8080/v1/models until 200 OK or T/O    │
│  4. client = LLMClient(profile)   # openai SDK pointed at base_url   │
│  5. workflow.run(client, input)                                      │
│       ├─ load prompt template (prompts/terraform_reviewer.md)        │
│       ├─ render with {input_text}                                    │
│       ├─ stream chat completion → stdout (live tokens)               │
│       └─ also collect full text                                      │
│  6. render.write_review_md(text) → outputs/<ts>-review.md            │
│  7. server.stop()    # registered via atexit + SIGINT/SIGTERM hooks  │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. Repo layout

```
local-model-playground/
├── pyproject.toml              # uv-managed; declares gcp-agent script entry
├── README.md                   # rewritten quickstart
├── docs/
│   ├── idea.md                 # existing brief (untouched)
│   └── superpowers/specs/      # this design doc + later plan
├── profiles/
│   ├── light.yaml              # written for schema parity, not exercised in v1
│   └── heavy.yaml              # the v1 target
├── prompts/
│   ├── system.md
│   └── terraform_reviewer.md
├── examples/
│   └── terraform/
│       └── service-account-bad-editor.tf
├── src/gcp_agent_playground/
│   ├── __init__.py
│   ├── main.py                 # typer app
│   ├── profiles.py             # YAML load + pydantic Profile model
│   ├── server.py               # MLXServer subprocess lifecycle
│   ├── llm_client.py           # openai SDK wrapper, streaming helper
│   ├── workflows.py            # chat() + review() functions
│   └── render.py               # output Markdown writer
├── tests/
│   └── test_smoke.py           # gated end-to-end test
├── outputs/                    # gitignored except .gitkeep
└── notes/
    ├── lessons-learned.md      # filled in as v1 is exercised
    └── future-hardening.md     # everything deferred from v1 + the brief's deferred list
```

## 4. Module design

Each module has one clear purpose. A consumer should be able to use any of them by reading its function/class signatures alone.

### 4.1 `profiles.py`

```python
class Profile(pydantic.BaseModel):
    name: str
    description: str
    runtime: Literal["mlx"]
    model: str
    host: str = "127.0.0.1"
    port: int = 8080
    base_url: str                    # http://{host}:{port}/v1
    temperature: float = 0.3
    max_tokens: int = 4000
    intended_use: list[str] = []

def load(name: str, profiles_dir: Path = Path("profiles")) -> Profile
```

Reads `profiles/{name}.yaml`, validates via pydantic, returns `Profile`. No I/O beyond that read.

### 4.2 `server.py`

```python
class MLXServer:
    def __init__(self, profile: Profile): ...
    def start(self, ready_timeout_s: float = 120) -> None
    def stop(self, term_grace_s: float = 5) -> None
    def is_ready(self) -> bool        # GET {base_url}/models, expect 200
    def __enter__(self) -> "MLXServer"
    def __exit__(self, *exc) -> None
```

`start()`:
1. Probe `is_ready()` *before* spawning. If 200 already, raise — port is in use.
2. `subprocess.Popen(["mlx_lm.server", "--model", profile.model, "--host", profile.host, "--port", str(profile.port)])` with stdout/stderr piped to `outputs/.server-logs/<UTC-ts>.log`.
3. Poll `is_ready()` every 500 ms until 200 OK or `ready_timeout_s` elapses.
4. On timeout: kill the subprocess, raise with the tail (~20 lines) of the logfile in the message.
5. Register `atexit.register(self.stop)` and `signal.signal(SIGINT|SIGTERM, ...)` calling `stop()`.

`stop()`:
- SIGTERM, wait `term_grace_s`, SIGKILL if still alive. Idempotent.

### 4.3 `llm_client.py`

```python
class LLMClient:
    def __init__(self, profile: Profile):
        self.profile = profile
        self._client = openai.OpenAI(base_url=profile.base_url, api_key="not-needed")

    def stream_chat(self, messages: list[dict]) -> Iterator[str]
        # yields delta.content chunks
```

Thin wrapper over `openai.OpenAI().chat.completions.create(model=profile.model, messages=..., temperature=..., max_tokens=..., stream=True)`. Caller decides what to do with the chunks.

### 4.4 `workflows.py`

```python
SYSTEM_PROMPT = (Path("prompts/system.md")).read_text()

def chat(client: LLMClient) -> None:
    """Interactive REPL. Read user line → stream assistant reply → repeat. Ctrl-D / 'exit' to quit."""

def review(client: LLMClient, input_path: Path) -> Path:
    """One-shot review. Returns path to written review.md."""
    template = (Path("prompts/terraform_reviewer.md")).read_text()
    user_msg = template.format(input_text=input_path.read_text())
    chunks: list[str] = []
    for chunk in client.stream_chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        chunks.append(chunk)
    return render.write_review_md("".join(chunks), source=input_path, profile=client.profile)
```

Two functions. The contract: take a client, do one workflow, return whatever the user needs.

### 4.5 `render.py`

```python
def write_review_md(body: str, *, source: Path, profile: Profile,
                    out_dir: Path = Path("outputs")) -> Path
```

Writes `outputs/<UTC-timestamp>-review.md` with a small header (source path, profile name, model slug, timestamp) followed by `body`. Timestamps use ISO-8601 with `:` replaced by `-` for filesystem safety (e.g. `2026-05-05T14-32-07Z-review.md`).

### 4.6 `main.py`

```python
app = typer.Typer(no_args_is_help=True)

@app.command()
def chat(profile: str = "heavy") -> None: ...

@app.command()
def review(input: Path = typer.Argument(..., exists=True, dir_okay=False),
           profile: str = "heavy") -> None: ...
```

Both commands follow the same shape: load profile → start server (context manager) → build client → call workflow → return.

`pyproject.toml` declares `gcp-agent = "gcp_agent_playground.main:app"` as the script entry.

## 5. First-slice file content

### `profiles/heavy.yaml`

```yaml
name: heavy
description: "128 GB MacBook profile for deeper local synthesis"
runtime: mlx
model: <slug-discovered-during-setup>   # e.g. mlx-community/gemma-3-27b-it-4bit
host: 127.0.0.1
port: 8080
base_url: http://127.0.0.1:8080/v1
temperature: 0.3
max_tokens: 4000
intended_use:
  - larger Terraform review
  - deeper GCP reasoning
```

### `profiles/light.yaml`

Same shape; `model:` left as a TODO placeholder. v1 doesn't exercise this profile — written only so profile swapping is mechanically validated.

### `prompts/system.md`

The brief's minimal system prompt verbatim:

> You are a local AI assistant for learning GCP infrastructure engineering, Terraform, cloud security, and agentic AI harness design.
>
> This is a proof-of-concept playground. Use fake examples only. Provide practical engineering advice, identify assumptions, explain risks, and suggest validation steps.
>
> Do not claim something is production-ready. Distinguish explanation, recommendation, and evidence. Prefer clear, structured output.

### `prompts/terraform_reviewer.md`

```text
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

```hcl
{input_text}
```
```

### `examples/terraform/service-account-bad-editor.tf`

The brief's exact example, prefaced with one comment line:

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

### `outputs/`

Gitignored except `.gitkeep`. `outputs/.server-logs/` is also gitignored.

### `notes/future-hardening.md`

Bullet list combining the brief's "Deferred Hardening Notes" verbatim plus the items deferred from v1: `compare` command, static Terraform checks, JSON output artifact, `acceptance_to_validation` prompt, `gcp_tutor` prompt, `tickets/` examples, comparison table, lessons-learned synthesis, light-profile validation.

### `pyproject.toml`

```toml
[project]
name = "gcp-agent-playground"
version = "0.1.0"
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
```

(Repo lives under `~/code`, not `~/iCloud`, so the global `tool.uv.project-environment` rule does not apply — default in-repo `.venv` is correct.)

### `README.md`

Rewritten, short. Quickstart only:

1. `uv sync`
2. Pull the chosen MLX model (`huggingface-cli download <slug>`).
3. `uv run gcp-agent chat --profile heavy`
4. `uv run gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf`

Pointers to `docs/idea.md`, this design doc, and `notes/future-hardening.md`.

## 6. Error handling

POC strategy: fail fast, descriptive message, non-zero exit. No retries, no fallbacks.

| Failure                                          | Where                              | Behavior                                                                                                                                  |
| ------------------------------------------------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Profile file missing                             | `profiles.load`                    | `Profile '<name>' not found at profiles/<name>.yaml` → exit 2                                                                             |
| Profile YAML malformed / fails schema            | pydantic `ValidationError`         | Print field-by-field validation errors → exit 2                                                                                           |
| `mlx_lm.server` binary not on PATH               | `Popen` → `FileNotFoundError`      | `mlx_lm.server not found. Did you 'uv sync'?` → exit 2                                                                                    |
| Server fails to become ready before timeout      | `MLXServer.start`                  | Kill subprocess, print last ~20 lines of the logfile so the user sees model-load errors → exit 3                                          |
| Port already in use (something already serving)  | pre-spawn probe                    | `Port <port> is already serving a model. Stop the existing server or change the port.` → exit 4                                           |
| Model slug not pulled / load error inside server | server log                         | Surfaces via the "fails to become ready" path                                                                                             |
| Input file missing for `review`                  | typer's `exists=True`              | Standard typer error → exit 2                                                                                                             |
| Connection drops mid-stream                      | openai SDK exception               | Print the exception message + path of any partial output → exit 5                                                                         |
| Ctrl-C during streaming                          | `KeyboardInterrupt`                | Signal handler calls `MLXServer.stop()`. No half-files written. → exit 130                                                                |
| Output dir not writable                          | `render.write_review_md`           | `PermissionError` propagates with the resolved path                                                                                       |

### Cleanup invariants

1. `MLXServer` is always entered as a context manager from `main.py`.
2. `start()` registers `atexit` + `SIGINT`/`SIGTERM` handlers calling `stop()`.
3. `stop()` is idempotent.
4. Pre-spawn probe rejects port conflicts rather than letting `Popen` collide.

### Logging

`print` for user-facing output. Server stdout/stderr → `outputs/.server-logs/<UTC-ts>.log`. Logfile is gitignored. No structured logging in v1.

### Deliberately not handled in v1 (recorded in `notes/future-hardening.md`)

- Concurrent invocations / lock files
- Crashed-but-not-cleaned-up server processes / PID files
- Output schema validation (no JSON output yet)
- Retry on transient HTTP errors
- Model-output safety / redaction

## 7. Verification & definition of done

### 7.1 Automated smoke test (`tests/test_smoke.py`)

One test, gated:

```python
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="needs local mlx model")
def test_review_end_to_end(tmp_path):
    # Run: gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf
    # Assert: exit 0, outputs/<ts>-review.md created, contains
    #   "## Summary", "## Findings", "## Validation evidence", "## Open questions",
    #   and "roles/editor" appears in Findings.
```

Run via `RUN_LIVE=1 uv run pytest`.

### 7.2 Manual smoke checklist (recorded in `notes/lessons-learned.md`)

1. `uv sync` succeeds; `gcp-agent --help` lists `chat` and `review`.
2. `mlx_lm.server` launches and `/v1/models` responds within ~30 s on the heavy machine.
3. `gcp-agent chat --profile heavy` — ask "Explain workload identity federation in two paragraphs"; tokens stream; response is coherent.
4. `gcp-agent review --profile heavy examples/terraform/service-account-bad-editor.tf` finds `roles/editor` is overly broad, recommends a narrower role, includes Validation Evidence and Open Questions.
5. Ctrl-C during a long review → server process is gone (`ps aux | grep mlx_lm.server` returns nothing).
6. Re-running `review` produces a second `outputs/<ts>-review.md` (no overwrite).
7. With `--profile light` pointed at a smaller model, `chat` produces output (sanity check that profile swapping works).

### 7.3 Definition of done for v1

- All Section 5 files exist with the content specified.
- `gcp-agent chat` and `gcp-agent review` both run end-to-end on the heavy machine.
- The smoke test passes with `RUN_LIVE=1`.
- The manual checklist is walked once; surprises are recorded in `notes/lessons-learned.md`.
- `notes/future-hardening.md` lists every deferred item from the brief plus those deferred from v1.
- `README.md` quickstart works for someone following it from a clean clone.
- This design doc and the implementation plan are committed under `docs/superpowers/specs/`.

## 8. Open risks (called out, not solved)

1. **Model URI discovery.** The brief's `mlx-community/gemma-4-31b-it-4bit` slug may not exist. Implementation plan must include "verify model availability before everything else" as the first task, with the chosen slug recorded in `profiles/heavy.yaml`.
2. **Server startup time.** Model load on the heavy profile may be 30 s–2 min. If worse than that, per-invocation `review` UX gets painful and we may need to revisit the daemon-mode question (deferred during brainstorming).
3. **`mlx_lm` version drift.** The `mlx_lm.server` CLI flags have shifted historically. The plan should pin a specific `mlx-lm` version and verify the flag shape on first install.
