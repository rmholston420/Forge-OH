# ADR-015 — Forge-OH end-to-end SWE-bench Verified sandbox

**Status:** Proposed
**Lock-in phase:** Stage-1H (Harness Engineering — new)
**Supersedes:** —
**Related:** ADR-013 (coder ratification), ADR-012 (dual-mode routing), ADR-011 (self-eval harness)

## Context

ADR-013 amendment #1 (2026-08-05) ratified Qwen3.6-27B INT4 AutoRound (c01) as the canonical Forge-OH coder, backed by F.1b's 3-scorer Model Council on curated debug/arch prompts (39.7-point Perplexity-gold margin). Amendment #2 was queued to validate that verdict against a public, domain-appropriate benchmark. F.3 was pivoted from LiveCodeBench-v6 to SWE-bench Verified for contamination and domain fit (see BUILD_LOG 2026-08-05 05:14 EDT).

F.3 as currently scoped is a **raw-LLM** SWE-bench Verified run (oracle mode) directly against c01 :8501. That measures c01's patch-synthesis quality in isolation, which is the right test for coder ratification.

It does NOT measure whether the shipping Forge-OH product — BFF + agent-server + OpenHands agent loop + preset routing + workspace — actually solves real SWE-bench Verified tasks. Investigation (2026-08-05 05:32 EDT, Colossus probes) confirmed two blockers to running SWE-bench Verified through the full Forge-OH stack:

1. **Preset routing does not point at c01.** Current seeded presets (`ap-1 = gpt-4o` default, `ap-2 = claude-opus-4`) both target external cloud models. No preset references the ratified local coder role.
2. **No per-run Docker sandboxing.** The agent-server operates on a shared `~/dev/forge-oh/workspace/` directory. There is no SWE-bench-compatible sandboxing wired in: `grep -rn 'workspace_bootstrap|sandbox_image|swe.bench|swebench|workspace_base'` returned zero hits across `bff/` and `openhands/` site-packages.

Neither blocker was in Action Plan v4 or reconciliation-plan-v1. Path B was extrapolated from the North Star ("workflow-based GUI wrapper over the entire OpenHands suite") and the ideal-ACA-v8 acceptance-test expectations, not from an explicit spec item.

## Decision

1. **F.3 (coder ratification) proceeds as-is on raw-LLM Path A.** ADR-013 amendment #2 lands on Path A pass@1 against Verified (500 tasks, oracle mode). This is the ratification signal.

2. **A new Stage-1H is added to the reconciliation-plan** covering end-to-end SWE-bench Verified acceptance via full Forge-OH stack. Stage-1H is a first-class product slice, not a bench slice.

3. **Stage-1H deliverables:**
   - `bff/services/swe_bench_sandbox.py` — new service. Given a SWE-bench Verified `instance_id`, pulls the pre-built `sweb.eval.x86_64.<instance_id>` image, spins up a per-run container, checks out the repo at `base_commit` inside it, exposes the container as the workspace root for the agent-server, applies the produced patch, runs FAIL_TO_PASS + PASS_TO_PASS tests, returns pass/fail.
   - `bff/routers/runs.py` — extend `CreateRunRequest` with optional `benchTask: { source: "swe-bench-verified", instance_id: str }`. When present, workspace bootstrap goes through `swe_bench_sandbox.py` instead of the default `~/dev/forge-oh/workspace/`.
   - `bff/db/agent_presets.py` — seed a new preset `ap-3 = forge-oh-local-coder` referencing `role="coder"` (routes to c01 :8501 via existing `model_router.py`). Added as **non-default** initially; default-flip happens in a separate follow-up commit after Stage-1H completes end-to-end.
   - Minimum viable UI: extend the existing new-run modal in `src/features/runs/` with an optional "Bench task" field — dropdown of Verified `instance_id`s (or free-text). No new page; reuses the existing runs modal per the North Star's "every backend has frontend, without gold-plating" reading.

4. **Sandbox scope is narrow.** `swe_bench_sandbox.py` handles SWE-bench Verified format only. Generalized per-run isolated workspaces (for arbitrary evals, or user-selected isolation) are explicitly deferred. Rationale: YAGNI + we don't yet know what shape a second eval type would take.

5. **Preset default-flip is deferred to a follow-up ADR** (call it 015a or a plain BUILD_LOG entry, not a new ADR) once Stage-1H completes end-to-end and the c01-via-preset routing is verified reversibly.

6. **ADR-013 amendment #3 becomes possible.** After Stage-1H is complete, rerun SWE-bench Verified through the full Forge-OH stack (Path B). If the product-level pass@1 diverges meaningfully from raw-LLM Path A pass@1, file amendment #3 documenting the divergence. If it agrees, file a shorter BUILD_LOG confirmation entry.

## Rationale

**Why split Path A ratification from Path B product validation:**
- ADR-013 is a *model* decision. Ratifying a model with an end-to-end product test conflates two variables (model quality + product loop correctness). If a Path-B-only test fails, the failure is unattributable.
- Public SWE-bench Verified leaderboard columns split "oracle" (raw-LLM) from "agent" (full loop). We should too, for the same reason.
- Path A can run overnight. Path B (per-task agent loop, ~15-30 min/task × 500 tasks) takes days. Coder ratification can't wait days.

**Why non-default preset:**
- Flipping `isDefault=True` from `ap-1` (gpt-4o) to `ap-3` (c01) changes the behavior of every UI-initiated run silently. Reversible commit, but the blast radius is real.
- Landing `ap-3` non-default first lets Stage-1H itself validate the preset routing works before it's the default.

**Why narrow sandbox scope:**
- We know exactly one eval format that needs sandboxing today: SWE-bench Verified. The Verified format is stable (published dataset, hand-graded, canonical image naming).
- A generalized "isolated per-run Docker workspace" surface has many unknowns (image lifecycle, secret injection, filesystem overlay strategy) that don't need answers before Stage-1H can land.
- If a second eval format shows up (LiveCodeBench-v7? Aider-poll?), refactor `swe_bench_sandbox.py` to a generalized `eval_sandbox.py` then. Cheaper than speculating now.

## Alternatives considered

1. **Postpone F.3 entirely, build Stage-1H first, then run Verified through Path B only.** Rejected: ADR-013 amendment #2 blocks dual-mode routing impl (per prior TODO), and Stage-1H is multi-day work. Would leave the coder unratified for a week+.
2. **Run Path B on 1 task inside the F.3 shakeout by manually cloning django and pointing agent-server at it.** Rejected: even a single task requires fixing preset routing (item 1 above) or bypassing presets (which the current BFF `CreateRunRequest` schema won't accept — `agentPresetId` is required). Not doable in a 30-min shakeout without spec changes.
3. **Substitute Path B in the shakeout with OpenHands' upstream `swe_bench` evaluator (bypassing BFF entirely).** Rejected: tests OpenHands SDK + c01, not Forge-OH. Doesn't answer the product question. If we're going to spend eval time, spend it measuring what we ship.
4. **Broad "per-run isolated workspace" port (not SWE-bench specific).** Rejected: YAGNI. See §Rationale.

## Consequences

**New files:**
- `docs/adr/015-swe-bench-sandbox.md` (this file)
- `docs/reconciliation-plan-stage-1H.md` (Stage-1H spec detail)
- (later, in Stage-1H impl slice) `bff/services/swe_bench_sandbox.py`
- (later, in Stage-1H impl slice) matching frontend field extension in `src/features/runs/`

**Modified files (Stage-1H impl slice, not this turn):**
- `bff/routers/runs.py` — extend `CreateRunRequest`
- `bff/db/agent_presets.py` — seed `ap-3`
- One follow-up commit: flip default from `ap-1` to `ap-3` post-verification

**Procedures:**
- Path B (full-Forge-OH SWE-bench Verified) becomes a first-class product acceptance test, not a bench slice.
- ADR-013 gets a possible amendment #3 after Stage-1H.
- No changes to F.1b ratification, no changes to F.3 Path A scope, no changes to the planner (ADR-013 planner ratification stands).

**Downstream ADRs / logs:**
- `docs/adr/README.md` — index row added.
- `BUILD_LOG.md` — Stage-1H queue entry (this turn).
- `SESSION_HANDOFF.md` — overwritten to reflect the split-track plan.
- `PORTING_LEDGER.md` — untouched (no OSS ported yet; Stage-1H impl may vendor bits of OpenHands' upstream `swe_bench` evaluator, TBD at impl time).

## Lock-in phase

Stage-1H — Harness Engineering (new). This is a new stage inserted between reconciliation-plan-v1's existing Stage 1 (Bootstrap) and Stage 2 (`ModelClient` port), specifically for harness / eval / acceptance-test infrastructure.

## References

- `docs/reconciliation-plan-stage-1H.md` — full Stage-1H spec detail
- `docs/adr/013-qwen36-27b-canonical-coder-planner.md` — coder + planner ratification (amendment #2 pending F.3)
- `docs/adr/012-dual-mode-model-routing.md` — role-based routing (upstream of preset routing to c01)
- `BUILD_LOG.md` — 2026-08-05 05:14 EDT (F.3 pivot), and the Stage-1H queue entry from this turn
- Action Plan v4 §North Star — "every backend capability must have a corresponding frontend surface"
- Ideal ACA-v8 §Acceptance tests — SWE-bench Verified is the reference agentic bench
- SWE-bench Verified dataset: `princeton-nlp/SWE-bench_Verified` (500 hand-curated tasks, MIT)
- SWE-bench harness: `princeton-nlp/SWE-bench` v4.1.0 (verified installed on Colossus 2026-08-05 05:20 EDT)
