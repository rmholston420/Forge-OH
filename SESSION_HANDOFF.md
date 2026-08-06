# Forge-OH Session Handoff — 2026-08-06 18:25 EDT

## Current build-sequencing position

- **Stage:** 8 · vLLM serving-infra config bundle
- **Slice:** 8.0b (planner-role mirror) — **CLOSED**
- **Ports in progress:** none
- **Next slice:** Slice 8.1 kickoff (per `docs/reconciliation-plan-stage-8.md` line 191 — placeholder; requires scope-drafting from `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` commit `8e093bc` + ADR-029 §D1-§D5)

## Completed this session (chronological)

1. Slice 8.0 attestation closed (30% pass@1 at 32k, 26.7% at 65k, seed variance confirmed via 3×3×2 probe). Commit `2b4fb9b`.
2. Slice 8.0b launcher change: mirrored flag bundle to `ops/vllm_launch_planner.sh`. Commit `b812f49`.
3. Slice 8.0b DoD verified on Colossus: argv clean, /v1/models reports 65k, VRAM peak 30,668 MiB stable under 30k-token real inference. Closeout committed and pushed.

## Live coder + planner state on Colossus

- **Coder** `:8501` — Qwen3.6-27B int4-AutoRound, 65k, fp8 KV, chunked prefill, no spec-decode. Attestation: 30% / 26.7% pass@1 (32k/65k).
- **Planner** `:8511` — DSR1-Distill-32B AWQ-marlin, 65k, fp8 KV, chunked prefill, no spec-decode. VRAM peak 30,668 MiB (~1.5 GiB headroom).
- **Auto-swap:** supervisor cold-starts vLLM on first request per role; coder ~3.5 min, planner ~86 s.

## Remaining before current Definition of Done

- None for Slice 8.0 / 8.0b.

## Open questions / awaiting user answer

- **Next slice choice** — Slice 8.1 kickoff requires scope-drafting from the Model-Council-Synthesis file + ADR-029 §D1-§D5. Estimated 30-60 min just to draft the slice contract before any executable work. Alternative: revisit deferred items (spec-decode alternative with a small draft model, or draft a planner-role bench for future §8.0c).

## Deferred items (both slices)

- **Spec-decode revisit** (both coder and planner) — the n-gram approach broke structured-diff generation. Follow-up needs either a small dedicated draft model (VRAM math + weight-download) or a different draft-token config to justify. Not on critical path.
- **Planner-role bench** — no canonical planner smoke exists; §8.0b DoD used argv+VRAM+one real inference in lieu. A proper planner bench (reasoning correctness, tool-call JSON validity, maybe reasoning-block escape rate) is a future §8.0c or a bench-methodology addition.
- **Planner VRAM tightness** — actual headroom (~1.5 GiB) is tighter than the napkin estimate (~2.8 GiB). Stable at concurrency=1; concurrent-request behavior at high load unverified. If we see eviction stalls, ADR the planner-specific 32k rollback.

## Exact next action

Read `docs/reconciliation-plan-stage-8.md` and `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (project files, commit `8e093bc`) side-by-side to draft Slice 8.1's scope, DoD, and stop condition. File the draft as a new §8.1 section in the plan companion. Then execute.

Alternative next action if spec-decode revisit is picked instead: identify a small draft model (e.g. Qwen2.5-1.5B or similar) compatible with the coder's tokenizer, check VRAM budget (~1.5 GiB extra), and design the draft-token config with lower `num_speculative_tokens` to avoid the low-entropy mis-acceptance failure mode.

## Verification on next session start

```bash
cd ~/dev/forge-oh
# Confirm coder flags (if coder is up):
CID=$(docker ps --filter 'name=coder' --format '{{.ID}}' | head -1)
[ -n "$CID" ] && docker inspect --format '{{join .Args " "}}' "$CID" | tr ' ' '\n' | \
  grep -E 'speculative|kv-cache-dtype|chunked-prefill|long-prefill|max-model-len'

# Confirm planner flags (if planner is up):
CID=$(docker ps --filter 'name=planner' --format '{{.ID}}' | head -1)
[ -n "$CID" ] && docker inspect --format '{{join .Args " "}}' "$CID" | tr ' ' '\n' | \
  grep -E 'speculative|kv-cache-dtype|chunked-prefill|long-prefill|max-model-len|reasoning-parser|quantization'
```
