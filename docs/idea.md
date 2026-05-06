# GCP Agent Playground — Local Agentic AI POC Brief

## Purpose

This proof of concept explores whether local Apple-Silicon models can support lightweight agentic AI workflows for GCP infrastructure engineering, coding assistance, Terraform review, acceptance-criteria reasoning, and advisory synthesis.

The POC is explicitly a learning playground. It is not a production control system, not a compliance tool, and not intended to process corporate-sensitive data. The immediate goal is to learn the local model stack, compare light and heavy MacBook profiles, and build a simple harness that can advise on fake but realistic GCP infrastructure examples.

The intended downstream user of this brief is Claude Code. Claude Code should refine this brief, identify gaps, and produce an implementation plan using an agentic planning method such as the Superpowers plugin or an equivalent structured planning workflow.

## Context

The organization does not yet have local model workflows established for this class of work. This POC is meant to get ahead of the curve by experimenting locally with models, runtimes, and harness patterns before attempting any real corporate integration.

The target engineering domain is GCP cloud infrastructure in a banking, security, and corporate-controls environment. However, the POC must use synthetic examples only. Real JPMorgan Chase data, internal repositories, tickets, secrets, hostnames, project identifiers, or production infrastructure must not be used.

The user currently works mostly with Claude Code and VS Code. The POC should therefore produce a repo and workflow that is easy to inspect, easy to run locally, and suitable for iterative improvement with Claude Code.

## POC Thesis

Local models will not replace Claude Code or cloud-hosted frontier models in the near term. Their value is in becoming a local, inspectable, low-friction advisory layer that can support engineering workflows such as:

- Explaining GCP infrastructure concepts.
- Reviewing fake Terraform examples.
- Decomposing acceptance criteria into validation steps.
- Producing advisory Markdown and JSON artifacts.
- Comparing small-model and large-model behavior.
- Teaching harness engineering patterns around prompts, profiles, schemas, and deterministic checks.

The key learning objective is not raw model intelligence. The key learning objective is how to place a model inside a controlled local workflow.

## Non-Goals

This POC must not attempt to solve enterprise hardening yet.

Out of scope:

- Production GCP access.
- Live cloud mutation.
- Use of corporate-sensitive data.
- Use of real internal tickets or repositories.
- Processing secrets, tokens, certificates, account IDs, or customer data.
- Formal compliance approval.
- Enterprise data-loss prevention integration.
- Autonomous production agents.
- Full RAG implementation.
- Browser-based autonomous research loops.
- MCP tool sprawl.
- Multi-agent orchestration beyond simple profile comparison.

Deferred hardening topics:

- Corporate data classification rules.
- Redaction engine.
- Secret detection.
- Audit logging.
- Approval workflow.
- Security threat model.
- Policy-as-code integration.
- Enterprise model registry.
- Approved internal package distribution.

These topics should be captured as future work, not built in the first implementation.

## Target Machines

The POC should support two local MacBook profiles.

| Profile |            Machine | Purpose                                     |
| ------- | -----------------: | ------------------------------------------- |
| `light` |  M5 Max, 36 GB RAM | Fast local assistant for focused tasks.     |
| `heavy` | M5 Max, 128 GB RAM | Deeper synthesis and larger-context review. |

The same harness contract should work across both profiles. The models and runtime parameters may differ, but the commands, prompts, and output artifacts should remain comparable.

## Model Profiles

### Light Profile

The light profile targets standard 36 GB M5 Max MacBooks.

Suggested model:

```text
mlx-community/gemma-4-e4b-it-8bit
```

Fallback model:

```text
mlx-community/gemma-4-e4b-it-4bit
```

Intended uses:

- Concept explanation.
- Small Terraform review.
- Acceptance-criteria decomposition.
- Prompt contract testing.
- Short advisory outputs.
- Fast local experimentation.

### Heavy Profile

The heavy profile targets 128 GB M5 Max MacBooks.

Suggested model:

```text
mlx-community/gemma-4-31b-it-4bit
```

Intended uses:

- Larger Terraform review.
- Multi-artifact synthesis.
- Deeper GCP IAM reasoning.
- Architecture advice.
- Comparison against light profile outputs.
- Longer advisory Markdown outputs.

## Runtime Direction

Use MLX as the initial local runtime.

The initial path should be:

1. Install `mlx-lm`.
2. Download or reference the selected MLX model.
3. Run direct generation smoke tests.
4. Run the local MLX OpenAI-compatible server.
5. Call the local server from a small Python client.
6. Build the CLI harness around that client.

The server should bind to localhost only.

Example server shape:

```bash
mlx_lm.server \
  --model mlx-community/gemma-4-e4b-it-8bit \
  --host 127.0.0.1 \
  --port 8080
```

For the heavy profile:

```bash
mlx_lm.server \
  --model mlx-community/gemma-4-31b-it-4bit \
  --host 127.0.0.1 \
  --port 8080
```

## Harness Goal

Build a small Python CLI named something like:

```text
lmp
```

The CLI should support three initial modes:

```text
chat       Ask local model questions about GCP, Terraform, IAM, or agentic AI.
review     Review a fake GCP/Terraform/ticket example and produce advisory output.
compare    Run light and heavy profiles against the same input and compare outputs.
```

Example commands:

```bash
lmp chat --profile light

lmp review \
  --profile light \
  examples/terraform/service-account-bad-editor.tf

lmp review \
  --profile heavy \
  examples/tickets/service-account.md

lmp compare \
  examples/terraform/service-account-bad-editor.tf
```

## Agentic Scope

Keep agentic behavior modest in the first implementation.

Acceptable first agent loop:

1. Read input.
2. Classify task type.
3. Select prompt template.
4. Call local model.
5. Validate basic output shape.
6. Write Markdown and optional JSON artifacts.
7. Ask the user what to do next.

Optional deterministic additions:

- Run simple static checks on Terraform text.
- Detect obviously broad IAM roles such as `roles/editor`, `roles/owner`, and `roles/viewer`.
- Detect service account key resources.
- Summarize deterministic findings before asking the model for advisory synthesis.

Avoid in the first implementation:

- Live GCP commands.
- Web search.
- Browser automation.
- Autonomous repo edits.
- Multi-step self-directed plans.
- MCP integration.
- Corporate integrations.

## Synthetic Use Cases

### Use Case 1: GCP IAM Service Account Review

Input: fake Terraform defining a service account and an overly broad IAM binding.

Example issue:

```hcl
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

Expected advisory behavior:

- Identify `roles/editor` as overly broad.
- Explain why primitive or broad project-level roles are risky.
- Recommend narrower role assignment.
- Suggest validation evidence such as IAM policy inspection.
- Avoid claiming production compliance.

### Use Case 2: Acceptance Criteria to Validation Plan

Input: fake implementation ticket.

Example:

```markdown
# Implementation Ticket

Create a GCP service account for a deployment pipeline.

Acceptance criteria:

- Service account exists.
- Pipeline can impersonate it.
- No user has direct access to the service account.
- Evidence is captured.
```

Expected advisory behavior:

- Extract implementation intent.
- Identify assumptions.
- Produce validation steps.
- List evidence to collect.
- Identify open questions.
- Explain what is not proven by the input alone.

### Use Case 3: GCP Concept Tutor

Example questions:

```text
Explain direct principal IAM binding versus group-based binding in GCP.
Explain workload identity federation.
Explain why API success is not the same as postcondition success.
Explain control plane versus data plane validation.
```

Expected advisory behavior:

- Explain concepts clearly.
- Use engineering language.
- Separate fact, recommendation, and uncertainty.
- Suggest practical validation approaches.

### Use Case 4: Local Coding Harness Experiment

Use a toy Python CLI repo to test local coding assistance.

Possible tasks:

- Add a new prompt template.
- Add a profile YAML loader.
- Add Markdown output rendering.
- Add a static Terraform check.
- Add a comparison command.

Claude Code may be used to implement the harness. Local Gemma is the model under test.

## Suggested Repository Layout

```text
local-model-playground/
  README.md
  pyproject.toml

  profiles/
    light.yaml
    heavy.yaml

  examples/
    tickets/
      service-account.md
      storage-bucket.md
      workload-identity.md
    terraform/
      service-account-good.tf
      service-account-bad-editor.tf
      service-account-key-bad.tf

  prompts/
    system.md
    gcp_tutor.md
    terraform_reviewer.md
    acceptance_to_validation.md

  src/
    local_model_playground/
      __init__.py
      main.py
      llm_client.py
      profiles.py
      workflows.py
      render.py
      static_checks.py

  outputs/
    .gitkeep

  notes/
    lessons-learned.md
    model-comparison.md
    future-hardening.md
```

## Profile YAML Examples

### `profiles/light.yaml`

```yaml
name: light
description: "36 GB MacBook profile for fast local experiments"
runtime: mlx
model: mlx-community/gemma-4-e4b-it-8bit
base_url: http://127.0.0.1:8080/v1
temperature: 0.3
max_tokens: 2000
intended_use:
  - concept explanation
  - small Terraform review
  - acceptance criteria decomposition
  - prompt testing
```

### `profiles/heavy.yaml`

```yaml
name: heavy
description: "128 GB MacBook profile for deeper local synthesis"
runtime: mlx
model: mlx-community/gemma-4-31b-it-4bit
base_url: http://127.0.0.1:8080/v1
temperature: 0.3
max_tokens: 4000
intended_use:
  - larger Terraform review
  - multi-artifact synthesis
  - deeper GCP reasoning
  - architecture advice
```

## Minimal System Prompt

Use this as the initial system prompt:

```text
You are a local AI assistant for learning GCP infrastructure engineering, Terraform, cloud security, and agentic AI harness design.

This is a proof-of-concept playground. Use fake examples only. Provide practical engineering advice, identify assumptions, explain risks, and suggest validation steps.

Do not claim something is production-ready. Distinguish explanation, recommendation, and evidence. Prefer clear, structured output.
```

## Initial Output Artifacts

For review workflows, generate:

```text
review.md
review.json
open-questions.md
model-notes.md
```

Optional later artifacts:

```text
static-findings.json
comparison.md
lessons-learned.md
future-hardening.md
```

## Evaluation Questions

The POC should collect observations, not formal benchmark scores.

Track:

- Does the light model catch obvious GCP/IAM issues?
- Does the heavy model produce materially better advice?
- Does either model overclaim evidence?
- Can the model follow the requested output shape?
- How responsive is the model on each MacBook profile?
- How much memory pressure is observed?
- What tasks are useful locally?
- What tasks still require Claude Code or frontier cloud models?

Suggested comparison table:

| Test                      | Light Result | Heavy Result | Notes |
| ------------------------- | ------------ | ------------ | ----- |
| Explain service accounts  | TBD          | TBD          | TBD   |
| Detect `roles/editor`     | TBD          | TBD          | TBD   |
| Generate validation plan  | TBD          | TBD          | TBD   |
| Review multi-file example | TBD          | TBD          | TBD   |
| Follow JSON shape         | TBD          | TBD          | TBD   |

## POC Success Criteria

The POC succeeds if it demonstrates the following:

- Gemma 4 light and heavy profiles can run locally on the intended MacBook classes.
- The models can be exposed through a local OpenAI-compatible endpoint.
- A small Python CLI harness can call the local model.
- The harness can advise on synthetic GCP/Terraform examples.
- The harness can compare light and heavy model outputs.
- The team can identify which tasks local models handle well.
- The team can identify which tasks require cloud models, human review, or future hardening.

## Deferred Hardening Notes

Capture these in `notes/future-hardening.md`, but do not implement them in the first pass:

- Redaction and secret scanning.
- Corporate data handling rules.
- Local log retention policy.
- Prompt/output audit trail.
- Policy-as-code integration.
- Terraform plan JSON parsing.
- Read-only GCP validation commands.
- Approval workflow.
- Threat model.
- Enterprise packaging.
- Internal model approval process.

## Suggested Claude Code Assignment

Claude Code should refine this POC brief and produce an implementation plan.

The implementation plan should include:

1. A clarified problem statement.
2. A phased build plan.
3. A minimal viable CLI design.
4. Proposed Python package structure.
5. Dependencies and installation approach.
6. Profile-loading design.
7. Local model client design.
8. Prompt-template design.
9. Review workflow design.
10. Compare workflow design.
11. Synthetic examples to create.
12. Test strategy.
13. Risks and deferred hardening.
14. First implementation tasks suitable for Claude Code execution.

Claude Code should use a structured planning method such as the Superpowers plugin or an equivalent planning workflow. The first Claude Code task is planning only. It should not immediately implement the project until the plan is reviewed.

## First Implementation Slice

The recommended first build slice is intentionally small:

1. Create a Python CLI skeleton.
2. Add profile YAML loading.
3. Add an OpenAI-compatible local model client.
4. Add a `chat` command.
5. Add a `review` command that accepts a text file.
6. Add one prompt template for Terraform review.
7. Add one fake Terraform example.
8. Write `review.md` to `outputs/`.

After that works, add:

1. Static Terraform text checks.
2. JSON output.
3. Light/heavy comparison.
4. More synthetic examples.
5. Lessons-learned notes.

## Working Assumption

The core assumption to validate is:

```text
A small local harness around MLX-hosted Gemma models can provide useful advisory support for GCP infrastructure engineering examples, while teaching practical harness engineering patterns that may later inform more formal enterprise AI workflows.
```
