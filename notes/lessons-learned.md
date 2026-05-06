# Lessons learned

This file is filled in as v1 is exercised. After walking the manual smoke checklist (see `docs/superpowers/specs/2026-05-05-gcp-agent-playground-design.md` §7.2), record:

- Surprises during install or first run
- Cold-start time observed for the heavy profile
- Quality observations on the synthetic Terraform review
- Any flag/CLI shape changes in `mlx_lm.server` we had to work around
- Tasks the local model handled well vs. tasks where it underperformed

## Model-slug discovery saga (Task 1 follow-up)

The brief named `mlx-community/gemma-4-31b-it-4bit`. That slug **does** exist on Hugging Face but is multimodal (image-text-to-text) and requires `mlx_vlm`, not `mlx_lm.server`. The same trap exists across the whole `gemma-3-Nb-it-*` and `gemma-4-Nb-it-*` series: any `-it-` instruction-tuned slug without `text` in the name is multimodal.

Sequence we walked:

1. `mlx-community/gemma-2-27b-it-4bit` — text-only, `mlx_lm`-compatible, but the 4-bit weights are broken: `mlx_lm.generate` produces pure `<pad>` tokens for any prompt (verified by bypassing `mlx_lm.server` entirely). Avoid.
2. `mlx-community/gemma-2-9b-it-4bit` — smaller fallback we briefly switched to, but never tested live because we found a better Gemma 3 option.
3. `mlx-community/gemma-3-text-27b-it-4bit` — **the right answer**. Explicit `text-` in the slug means the explicitly text-only sibling of the (multimodal) `gemma-3-27b-it-4bit`. Instruction-tuned, ~16 GB on disk, fits the heavy profile cleanly.

Two more text-only Gemma options exist if needed:

- `mlx-community/gemma-3n-E4B-it-lm-4bit` — Gemma 3n architecture, ~7B effective params (smaller, faster).
- `mlx-community/gemma-3-1b-it-4bit` — tiny, would suit a future light profile.

Server flags actually exercised:

- `mlx_lm.server --use-default-chat-template` — we added this when chat templates first looked off; turned out the underlying issue was the broken Gemma 2 27B 4-bit quant, not the template. Keeping the flag is harmless but not strictly necessary once a known-good model is in place.

Workflow change forced by Gemma's chat template:

- Gemma's tokenizer chat template raises `'System role not supported'` if `messages[0].role == 'system'`. `workflows.py` was updated to merge the system prompt into the first user message (`_prepend_system`). This is permanent; Gemma 2/3/4 all share that constraint.
