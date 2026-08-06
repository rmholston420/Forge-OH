# Forge-OH Session Handoff — 2026-08-06 18:05 EDT

## Current build-sequencing position

- **Stage / phase:** Stage 8 · Slice 8.0 (SDK-native vLLM serving-infra config) — **CLOSED**
- **Plugin / kernel component:** none active. Slice 8.0 ships as the new coder default.
- **Ports in progress:** none
- **Next slice:** Stage 8 · Slice 8.1 per `docs/reconciliation-plan-stage-8.md` (not yet scoped in this session)

## Completed this session

- **Slice 8.0 flag bundle applied and verified** (`ops/vllm_launch_coder.sh`, commit `56bb2e3`).
- **Bench harness alignment**: fixed port drift `:8000` → `:8501`, `--concurrency` dead flag removed, `--tasks all` semantic fix, `served-model-name` field wire-through, env overrides `FORGE_BENCH_CODER_URL` + `FORGE_BENCH_MAX_MODEL_LEN` (commits `0ed48e5`, `a9fb99a`, `3d0f59a`, `3954ad2`, `a98f390`).
- **Spec-decode ablation** (commit `ee6b55c`): removed `--speculative-config ngram` after Step 1 smoke returned pass@1 = 0/26 vs 33.3% baseline. Root-caused via `patch_raw` comparison: n-gram draft mis-acceptance was truncating `+++` filename headers on structured diff output. Documented in DEBUG_LOG 16:32 EDT.
- **Attestation complete** (see BUILD_LOG 18:05 EDT):
  - Step 1 matched-context 32k, no-spec: pass@1 = 30.0% (9/30) — within ±1 of 33.3% baseline
  - Step 2 65k, no-spec: pass@1 = 26.7% (8/30); 3 of 4 previously-context-skipped tasks recovered
  - Targeted noise-floor probe (3 × 3 × 2): confirmed Step 2 "-1 task" delta is seed variance; documented ±2-task pass@1 noise floor on 30-task smoke.

## Remaining before current DoD is met

**None. Slice 8.0 DoD is MET and closed.** Coder ships with the flag bundle in `ops/vllm_launch_coder.sh`.

## Open questions / awaiting answer

- **Spec-decode revisit (deferred, not blocking):** F.19-pre research called for `--speculative-config ngram`; Slice 8.0 shipped without it after malformed-header regression. Future work: evaluate an alternative draft model (e.g. n-gram with lower `num_speculative_tokens`, or a small dedicated draft model) that doesn't break structured-diff generation. Not scoped as a slice yet.
- **sphinx-7590 (100k prompt):** permanently exceeds the 65k ceiling; only way to recover is a further ceiling raise (would need VRAM math redo) or a prompt-compression step in the harness. Not scoped.

## Exact next action

**On next session start:** decide whether to begin Slice 8.1 (per `docs/reconciliation-plan-stage-8.md`) or to open a scoped probe on spec-decode alternatives. Reconciliation plan is the canonical planning doc per `AGENTS.md` § Canonical Planning Documents.

```bash
# Verify Slice 8.0 is still the live coder config on session resume:
cd ~/dev/forge-oh
CID=$(docker ps --filter 'name=coder' --format '{{.ID}}' | head -1)
docker inspect --format '{{join .Args " "}}' "$CID" | tr ' ' '\n' | \
  grep -E 'speculative|kv-cache-dtype|chunked-prefill|long-prefill|max-model-len'
# Expected: --max-model-len 65536, --kv-cache-dtype fp8, --enable-chunked-prefill,
# --long-prefill-token-threshold 4096. NO --speculative-config line.

# Then read docs/reconciliation-plan-stage-8.md for Slice 8.1 scope.
```
