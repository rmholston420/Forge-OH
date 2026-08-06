# ADR-028: Stage 7 Deviation — Topology-First Reconciliation, Canonical §7 Items Folded to Deferred Tail, Capability Slices Renumbered to Stage 8

- **Status:** Ratified (2026-08-06)
- **Date:** 2026-08-06
- **Slice:** Stage 7 sequencing + Stage 8 initialization
- **Amends:**
  - `docs/reconciliation-plan-v1.md` §7 — replaces the terse in-place §7.1–§7.6 list with a pointer to the companion doc `docs/reconciliation-plan-stage-7.md`, and folds canonical items §7.2–§7.5 into a renumbered "deferred Stage-7 tail" (§7.6–§7.9). Canonical §7.6 (ACA-v8 explicit deferrals — LoRA, MLflow, Langfuse, voice I/O) moves to §7.10.
  - `docs/reconciliation-plan-stage-7.md` — reads as ratified, no textual amendment; its §7.0/§7.2/§7.3/§7.5 are the sub-stages this ADR defers.
- **Supersedes:** —
- **Related:**
  - `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (in the Perplexity project files repo, commit `8e093bc`) — capability-uplift plan whose slice numbering is renumbered by this ADR from `7.x` to `8.x`.
  - [ADR-019 (DozerDB consolidation)](./019-dozerdb-consolidation.md), [ADR-020 (Qwen3-Embedding)](./020-qwen3-embedding-default.md), [ADR-027 (`switch_llm` forwarding)](./027-runtime-model-switching-forwards-switch-llm.md).
  - `SESSION_HANDOFF.md` at 2026-08-06 11:49 EDT (Stage 6 exit gate green pre-transition, benchmark gate ahead of Stage 7).

## Context

Three planning documents now target the same "Stage 7" slot with incompatible sub-slice numbering and scope:

1. **`docs/reconciliation-plan-v1.md` §7 (in-repo canonical, master plan).** Six sub-slices: 7.1 docker-compose reconciliation + fix `Dockerfile.frontend`, 7.2 healthcheck fix, 7.3 next-auth removal, 7.4 webhook subscriber, 7.5 VSCode/VNC/browser takeover, 7.6 explicit ACA-v8 deferrals. Terse — 26 lines total.

2. **`Forge-OH-reconciliation-plan-v1-stage-7.md` (workspace draft companion, ratified into this repo by the same PR that lands this ADR as `docs/reconciliation-plan-stage-7.md`).** Six sub-slices: 7.0 baseline inspection, 7.1 docker-compose single-host topology reconciliation (detailed), 7.2 full-system regression pass, 7.3 resolve every deferred/flagged SDK-gap item, 7.4 documentation and ledger completeness audit, 7.5 final reconciliation closeout report. Detailed — 475 lines.

3. **`Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (2026-08-06 model-council output, in the Perplexity project files repo).** Eleven capability-uplift slices numbered 7.0, 7.0.5, 7.1–7.9 covering vLLM serving-infra bundle, measurement hardening, hermetic verification, execution-grounded repair, LLM-as-judge selection, tree-sitter localization, SBFL fusion, ACE playbook, memory re-query, Self-Refine, TVCACHE.

The three collide on sub-slice numbers 7.1–7.5. `SESSION_HANDOFF.md` (last update 2026-08-06 11:49 EDT) still points at "Stage 7.1 (docker-compose single-host topology rewrite)" as the exact next action — leaving unresolved *which* Stage 7.1 was meant.

Adjacent facts locked at the time of writing:

- The Stage 6 exit gate is reported green in `SESSION_HANDOFF.md` (pre-transition).
- The operator has explicitly waived the 30-task and 500-task SWE-bench Verified benchmark gates that `SESSION_HANDOFF.md` sequenced ahead of Stage 7. The current Stage-6 baseline (`~/.forge-oh/bench_pathF_swebench/20260806_1211_run/` on Colossus, Path A pass@1 = 33.3%, model c01) is treated as the reference point for future Stage 8 measurement.
- The companion Stage 7 doc did not exist in the repo prior to this ADR; it existed only in the workspace draft and in the Perplexity project files repo. The pattern established by Stages 2/4/6 is that a terse master §N in `docs/reconciliation-plan-v1.md` is expanded by a detailed `docs/reconciliation-plan-stage-N.md` companion. Stage 7 had no such companion; this ADR's PR creates it.

The `Forge-OH-reconciliation-plan-v1.md` governing rule ("backend and frontend ship together") applies unchanged; it is trivially satisfied by every Stage 7 sub-slice under this ADR (all infra/ledger, no new endpoints or UI) and imposed on every Stage 8 capability slice.

## Decision

Execute a hybrid, topology-first Stage 7 and renumber the Council-Synthesis capability slices to Stage 8. Precisely:

### 1. Adopt the workspace-attachment Stage 7 companion as canonical

The workspace draft `Forge-OH-reconciliation-plan-v1-stage-7.md` becomes `docs/reconciliation-plan-stage-7.md` in the same PR that lands this ADR. It supersedes the terse in-place `docs/reconciliation-plan-v1.md` §7 for detailed execution. The master plan's §7 is rewritten in the same PR (see §3 below) to point at the companion doc and to fold the canonical §7.2–§7.6 items into a renumbered deferred tail.

### 2. Immediate Stage 7 scope — §7.1 + §7.4 of the companion doc land now

Two sub-stages from `docs/reconciliation-plan-stage-7.md` execute now, in this order:

- **§7.1 — `docker-compose.yml` single-host topology reconciliation.** Inventory every service accumulated across Stages 1–6 (bff, frontend, dozerdb from Stage 4, qdrant from Stage 5, searxng from Stage 6), fold any standalone containers into compose with correct `env_file` sourcing, confirm no duplicate `volumes:` keys, document the host-process-vs-containerized split in `docs/deployment-topology.md`, and add `scripts/start-host-services.sh` for the host-side inference engines. Execute via option-C hybrid (read-only Colossus dump → cloud PR → Colossus verify).
- **§7.4 — Documentation and ledger completeness audit.** Confirm every port from Stages 4–6 has a `PORTING_LEDGER.md` entry with a resolvable commit hash. Donor-repo hash resolution runs against **`rmholston420/kosmos` on GitHub** (via `gh api repos/rmholston420/kosmos/commits/<hash> --jq .sha`), not a local `~/dev/kosmos-reference` checkout. Confirm no `.env`-family secret files are staged or tracked.

Both are pure infra/ledger — no new backend endpoints, no new UI. The BE+FE-together rule is satisfied by construction.

### 3. Canonical §7.2–§7.5 folded to renumbered deferred tail — 7.6 through 7.9

The four in-repo canonical §7 items that are not addressed by the companion doc are folded into a renumbered deferred Stage-7 tail. They run alongside companion `§7.0/§7.2/§7.3/§7.5` **after Stage 8 completes**:

| New ID | Content | Source | Rationale for deferral |
|---|---|---|---|
| **§7.6** | Healthcheck fix — `src/app/api/health/route.ts` returning `{ok: true}`; point Dockerfile healthcheck at it. | Was canonical §7.2 | Purely infra hygiene; no upstream dependency on capability slices. |
| **§7.7** | Remove `next-auth` vestige — strip dependency + `NEXTAUTH_SECRET`/`NEXTAUTH_URL` CI env vars. | Was canonical §7.3 | Dead-code cleanup; single-user local system, auth is out of scope. |
| **§7.8** | Webhook subscriber — `bff/services/webhook_dispatcher.py` + settings-page target URL field. | Was canonical §7.4 | BE+FE-together slice; deliberately not run at the same time as capability work to avoid mingling infra hygiene with new behavior. |
| **§7.9** | VSCode / VNC / live browser takeover — proxy agent-server session URLs through BFF; new embedded iframe tabs. | Was canonical §7.5 | Highest integration cost, lowest ROI per canonical §7 own wording. |
| **§7.10** | Explicit ACA-v8 deferrals — LoRA/QLoRA (Axolotl/Unsloth, Blackwell FP4/NVFP4), MLflow champion/challenger, Langfuse tracing, voice I/O (whisper.cpp/Piper). | Was canonical §7.6 | Numbered later of the renumbering; unchanged in content — still explicit "revisit based on actual need" items. |

`docs/reconciliation-plan-stage-7.md` companion items `§7.0/§7.2/§7.3/§7.5` (baseline inspection, full regression, deferred-items resolution, closeout report) remain deferred to post-Stage-8 as originally scoped: running them now would only need to be re-run after Stage 8 modifies the tree.

### 4. Renumber Council-Synthesis capability slices — 7.x → 8.x

The Council-Synthesis document (in the Perplexity project files repo, commit `8e093bc`) proposes slices numbered 7.0 through 7.9. To eliminate the collision with the reconciliation-plan Stage 7 slice numbers governed by this ADR, those slices become Stage 8.0 through 8.9. The mapping (1:1):

| Council-Synthesis (old) | Canonical Forge-OH ID (new) | Title |
|---|---|---|
| 7.0 | **8.0** | vLLM infra config bundle (APC + spec-decode + fp8 KV-cache + chunked prefill) |
| 7.0.5 | **8.0.5** | Measurement hardening (McNemar, paired seeds, expand smoke ≥100, cost-per-solved-task telemetry) |
| 7.1 | **8.1** | Hermetic verification primitive |
| 7.2 | **8.2** | Bounded execution-grounded repair loop |
| 7.3 | **8.3** | Selection layer (deterministic gates + LLM-as-judge tie-break) |
| 7.4 | **8.4** | Path B autonomous localization (tree-sitter + hierarchical) |
| 7.5 | **8.5** | SBFL fusion (on-demand) |
| 7.6 | **8.6** | ACE-style skill playbook with token budget cap |
| 7.7 | **8.7** | Task-conditioned memory re-query |
| 7.8 | **8.8** | Self-Refine plan critique (A/B) |
| 7.9 | **8.9** | Tool-call memoization (TVCACHE-style) |

The Council-Synthesis document in the Perplexity project files repo was rewritten in-place under commit `8e093bc` to reflect the Stage 8 IDs canonically. Any external artifact (chat log, deep-research subagent output, prior commit body) that references the old `7.x` numbers is superseded by this ADR.

The Council-Synthesis-flagged 1-hour pre-slice investigation (do OpenHands SDK 1.40+ Microagents / Context Condensation / Pluggable Runtime already cover 8.1 / 8.6 / 8.2?) remains a pre-slicing research spike, not a slice, and runs before Stage 8.0.

### 5. Benchmark gate explicitly waived for the Stage-6 → Stage-7 transition

The 30-task and 500-task SWE-bench Verified benchmark runs sequenced ahead of Stage 7 by `SESSION_HANDOFF.md` (2026-08-06 11:49 EDT) are explicitly skipped for this transition, per operator direction. Rationale: the current Stage 6 baseline (`~/.forge-oh/bench_pathF_swebench/20260806_1211_run/`, pass@1 = 33.3%) is already the reference point Stage 8 will measure against; re-running the same 30-task smoke against the same code before topology reconciliation would not change any decision that follows. Benchmark discipline is not abandoned — Stage 8.0.5 re-baselines against an expanded ≥100-task smoke with McNemar telemetry as its first act, superseding the current 30-task point estimate.

### 6. Definition of Done for Stage 7 under this deviation

Stage 7 is complete when *all* of the following hold:

1. `docs/reconciliation-plan-stage-7.md` §7.1 exit checklist (docker-compose reconciliation) passes on Colossus.
2. `docs/reconciliation-plan-stage-7.md` §7.4 exit checklist (ledger + `.gitignore` audit) passes.
3. `BUILD_LOG.md` records both §7.1 and §7.4 completions with timestamps.
4. `SESSION_HANDOFF.md` is overwritten to reflect Stage 8 (SDK-native investigation spike + Slice 8.0) as the exact next action.

Companion §7.0/§7.2/§7.3/§7.5 and this-ADR §7.6–§7.10 are **not** required for the Stage 7 DoD as scoped here; they are scheduled to run after Stage 8 as the true reconciliation-plan-v1 closeout.

## Consequences

**Positive**

- Every slice number in the repo now uniquely identifies exactly one slice across all three plans.
- The workspace-draft Stage 7 companion becomes part of the repo's `docs/` tree, matching the existing Stages 2/4/6 pattern, and is discoverable from `AGENTS.md § Canonical Planning Documents` via `docs/reconciliation-plan-v1.md` §7's pointer.
- Capability work (Stage 8) begins immediately after two topology/ledger prerequisites; there is no waiting behind the full closeout arc, and no closeout report is written before the code it describes is final.
- The four canonical §7 items (healthcheck, next-auth, webhook, VSCode/VNC) are preserved rather than dropped — they are simply moved to run after the capability work with new IDs, and their BE+FE-together character is honored where applicable (webhook = §7.8).
- The 30/500 benchmark waiver is documented with rationale and a replacement measurement path (Stage 8.0.5), so no future session re-litigates whether the benchmarks were "missed."

**Negative**

- Reconciliation-plan-v1's self-description ("Stage 7 is the last stage") is now false. Superseded by the ADR-028 pointer that this PR adds to `docs/reconciliation-plan-v1.md` §7.
- The old numbering (canonical §7.2 = healthcheck, §7.3 = next-auth, §7.4 = webhook, §7.5 = VSCode/VNC, §7.6 = ACA-v8) is preserved only in the pre-ADR-028 git history of `docs/reconciliation-plan-v1.md`. Anyone reading a pre-ADR-028 BUILD_LOG entry referencing "canonical §7.2" must consult this ADR to reconcile.
- Companion §7.2 (full-system regression) is not run against the current Stage-6-complete tree before Stage 8 begins. If a latent Stage-6 regression exists that Stage 6.7's own exit gate did not catch, Stage 8 work will accumulate on top of it. Mitigated by (a) `SESSION_HANDOFF.md`'s green-exit-gate claim, (b) Stage 8.0 being pure vLLM restart with no code changes, (c) Stage 8.0.5 running the full expanded smoke as its first act.

**Neutral**

- Company §7.1 and §7.4 execution order is fixed as §7.1 first, §7.4 second — §7.4's ledger audit inspects references that §7.1 does not touch, so the ordering is a preference for finishing the higher-visibility topology change before doing the pure-audit sweep.
- The renumbered §7.6–§7.10 items each carry their original canonical scope unchanged; only their slice IDs change.
- The pre-Stage-8 SDK-native investigation spike is 1 hour and is not itself a slice.

## Alternatives considered

- **Alt-A: Execute canonical §7.1–§7.6 in the original numbering as written, treat the workspace draft as auxiliary notes, and run Council-Synthesis after as Stage 8.** Rejected because the workspace draft is substantially more detailed than the canonical §7 (475 lines vs. 26 lines), it references post-canonical realities (Stage 6.7.5, DozerDB consolidation, Zetesis defer) that the canonical §7 predates, and it is what recent operator-facing planning has been anchored against.
- **Alt-B: Merge canonical §7 with the workspace draft into one flat renumbering (7.1–7.11 or similar), no companion doc, no ADR-028.** Rejected because it would require editing `docs/reconciliation-plan-v1.md` §7 into a 475-line block, breaking the existing master-terse / companion-detailed pattern used for Stages 2/4/6.
- **Alt-C: Execute Council-Synthesis as Stage 7, drop the workspace draft, and keep canonical §7 in its original form.** Rejected because §7.1 (docker-compose reconciliation) has direct upstream impact on the vLLM config bundle in Council-Synthesis 8.0 (host-vs-container topology decisions for the inference stack), and the ledger discipline in companion §7.4 is a hard project-instructions requirement independent of what comes next.
- **Alt-D: Do the deviation but track it in `BUILD_LOG.md` only, no ADR.** Rejected because the project instructions require ADR-level treatment for load-bearing sequencing changes, and the slice-number collision alone is load-bearing.

## Rollout

The following file changes land in one PR ("Stage 7 deviation · ADR-028") against `main`:

1. **New file**: `docs/adr/028-stage-7-deviation-topology-first-capability-slices-renumbered.md` (this ADR).
2. **New file**: `docs/reconciliation-plan-stage-7.md` (workspace draft canonicalized as the Stage 7 companion doc).
3. **Edit**: `docs/reconciliation-plan-v1.md` §7 — replace terse §7.1–§7.6 with a pointer to the companion doc and the renumbered `§7.6–§7.10` folded canonical items.
4. **Edit**: `docs/adr/README.md` — add ADR-028 index row.

Immediately after ratification (in a follow-up commit on the same branch or the merge commit itself):

5. **Append** to `BUILD_LOG.md` — one timestamped entry recording the ADR-028 filing and the two companion-doc pointers.
6. **Overwrite** `SESSION_HANDOFF.md` — Stage 7 (deviated) · §7.1 in progress · §7.4 next · deferred tail scheduled post-Stage-8; exact next action: request read-only Colossus topology dump for the §7.1 PR.

## Verification (already satisfied at ratification time)

- [x] Operator confirmed the four scope points (§7.1 + §7.4 now; §7.0/§7.2/§7.3/§7.5 defer; canonical §7.2–§7.6 fold to §7.6–§7.10; Council-Synthesis renumbers to 8.x).
- [x] Operator selected renumbering scheme "A" (numeric 7.6–7.10) over letter-based or umbrella alternatives.
- [x] Operator confirmed the amended plan targets `docs/reconciliation-plan-v1.md` in-repo canonical, not any workspace copy.
- [x] Operator explicitly waived the 30/500 benchmark gates for this transition.
- [x] Council-Synthesis renumbering was applied in the Perplexity project files repo prior to this ADR landing (commit `8e093bc`).

Post-ratification verification (during §7.1 and §7.4 execution):

- [ ] `docker compose down && docker compose up -d && docker compose ps` shows every accumulated containerized service healthy with no duplicate `volumes:` keys.
- [ ] Every commit hash referenced in `PORTING_LEDGER.md` resolves against `rmholston420/kosmos` on GitHub.
- [ ] No `.env`-family file appears in `git status --porcelain` or `git ls-files`.
