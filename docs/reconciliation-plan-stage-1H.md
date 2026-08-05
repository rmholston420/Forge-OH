# Forge-OH Reconciliation Plan v1 — Stage-1H (Harness Engineering: SWE-bench sandbox)

Companion to `Forge-OH-reconciliation-plan-v1.md` (in Perplexity project files) §6 "Harness Engineering Upgrades." Stage-1H is inserted between the plan's existing Stage 1 (Bootstrap) and Stage 2 (`ModelClient` port) for eval / acceptance-test infrastructure. Locked in by ADR-015.

## Scope

Enable end-to-end SWE-bench Verified execution through the full Forge-OH stack: browser UI → BFF → agent-server → per-task Docker sandbox → tests → result surfaces in UI.

Sandbox scope is narrow: SWE-bench Verified format only. Generalized per-run isolated workspaces are explicitly deferred (see ADR-015 §Rationale).

## Preconditions

- ADR-013 amendment #2 filed (F.3 Path A pass@1 result recorded). Stage-1H does not gate on this being any particular number — it gates only on the amendment existing, so the ratified coder identity is unambiguous when Stage-1H is implemented.
- Perplexity Computer sandbox → Colossus ssh access available for the impl slices (Stage-1H is not a Perplexity-Computer-only exercise; it edits real BFF code and requires actual container runs on Colossus).
- Disk headroom for SWE-bench Verified images: ~120 GB peak. Colossus currently has 372 GB free (verified 2026-08-05 05:20 EDT). Recheck before starting each impl slice.

## Deliverables

### 1H.1 — Preset `ap-3 = forge-oh-local-coder` (safe, non-default)

- **Files:** `bff/db/agent_presets.py`, `bff/db/seeds/agent_presets.json` (or equivalent seed path — verify against actual layout when impl starts).
- **Change:** add a third preset row with `role="coder"`, `isDefault=false`. Do NOT change `ap-1`'s `isDefault=true` in this slice.
- **Verify:** `curl -s http://127.0.0.1:8081/api/agent-presets | jq` shows all 3. POST /api/runs with `agentPresetId=ap-3` and `role="coder"` routes to `http://127.0.0.1:8501/v1` (c01) — confirm via `~/.forge-oh/bff.log`.
- **Stop condition:** ap-3 exists and routes correctly. Default remains ap-1.

### 1H.2 — `bff/services/swe_bench_sandbox.py` (SWE-bench Verified only)

- **Files:** new `bff/services/swe_bench_sandbox.py`; extend `bff/routers/runs.py::CreateRunRequest` with optional `benchTask` field; new tests in `bff/tests/`.
- **Behavior:**
  1. Given `benchTask.instance_id`, load the task from `princeton-nlp/SWE-bench_Verified` (HF datasets, cached).
  2. Pull `swebench/sweb.eval.x86_64.<instance_id>:latest` from Docker Hub (uses SWE-bench's public namespace — no local base-image builds required, verified via harness `--namespace swebench` default).
  3. `docker run` the image as a long-running container (name it `foh-eval-<run_id>`).
  4. Expose the container's `/testbed` as the agent-server workspace root. Agent operates inside the container via the OpenHands agent-server's existing exec surface (verify at impl time how workspace_base is wired for the sandboxed case).
  5. After the agent produces a patch, `docker exec` to apply it, then run FAIL_TO_PASS + PASS_TO_PASS test commands (from the task dict).
  6. Return the pass/fail + test output as run-completion metadata.
  7. Clean up: `docker rm -f foh-eval-<run_id>` on run completion (success or failure) unless a `benchTask.keepSandbox` debug flag is set.
- **Verify:** run django__django-10914 end-to-end from the UI. Passes if FAIL_TO_PASS tests go GREEN after agent-produced patch is applied inside the sandbox.
- **Stop condition:** 1 known-tractable task completes end-to-end from browser UI → visible pass/fail in the runs list.

### 1H.3 — Minimum UI field

- **Files:** `src/features/runs/NewRunModal.tsx` (or equivalent — verify path at impl start).
- **Change:** add an optional "Bench task" field: single-select `<Combobox>` of SWE-bench Verified `instance_id`s (fetched from a new BFF endpoint `GET /api/bench-tasks?source=swe-bench-verified`), or free-text `instance_id` entry. When set, POSTs with the `benchTask` field populated.
- **Verify:** dropdown lists at least 10 django Verified tasks. Selecting one then submitting produces a run that routes through the sandbox path.
- **Stop condition:** UI-initiated Verified run completes end-to-end.

### 1H.4 — Optional preset default flip (follow-up, one-line commit)

- After 1H.1–1H.3 all Green: flip `isDefault=true` from `ap-1` to `ap-3` in the seed data. Blast radius: every UI-initiated run silently defaults to c01 instead of gpt-4o. Reversible.
- No new ADR. `BUILD_LOG.md` entry only.
- **Stop condition:** default flipped, one full non-bench task run confirms the UI experience is unchanged aside from model identity.

### 1H.5 — Path B rerun on Verified (feeds possible ADR-013 amendment #3)

- After 1H.1–1H.3 all Green (default-flip 1H.4 optional at this point): rerun SWE-bench Verified through the full Forge-OH stack.
- Recommended subset: same 500 as Path A, or a stratified 100-task subset if wall time is prohibitive.
- Compare Path B pass@1 to Path A pass@1 (raw c01). Meaningful divergence → file ADR-013 amendment #3. Agreement → short BUILD_LOG confirmation.

## Definition of Done for Stage-1H (whole stage)

1H.1 + 1H.2 + 1H.3 all Green. 1H.4 and 1H.5 are Stage-1H follow-ups but not part of the exit gate.

## Exit gate (before Stage 2)

- ADR-013 amendment #2 filed (from Path A F.3 result — separate track, may complete first).
- ADR-015 ratified (this ADR moves from Proposed → Ratified after 1H.1–1H.3 all Green).
- No `"stub": True` in the SWE-bench sandbox path.

## Explicitly out of scope for Stage-1H

- Generalized per-run isolated workspaces (deferred; see ADR-015 §Rationale).
- Non-Verified SWE-bench variants (Lite, original, Pro) — add later if useful.
- Cross-language SWE-bench-style benches (multi-lingual) — deferred.
- Multi-workspace parallelism inside one run — deferred.
- Any Kosmos plugin integration — deferred to post-Forge-OH-standalone stages per Action Plan v4.
