> **STATUS AMENDMENT (2026-08-06 07:55 EDT):** Superseded by [ADR-026](./026-restart-from-here.md).
>
> Two evidence probes on 2026-08-06 invalidated ADR-025's load-bearing premises:
>
> 1. `scripts/6-4c-fork-worktree-probe.sh` (07:50 EDT) — forks inherit the parent's `workspace.working_dir` verbatim. A `git reset --hard` in "the fork's worktree" would destroy the parent's files.
> 2. `scripts/6-4c-patch-schema-inspect.sh` (07:54 EDT) — agent-server 1.40.0's `PATCH /api/conversations/{id}` `UpdateConversationRequest` schema exposes only `title` and `tags`. No workspace mutation is possible post-creation. The PATCH returned `200 {"success":true}` but silently discarded the workspace field.
>
> No possible amendment keeps this ADR's premise sound against agent-server 1.40.0's actual surface. ADR-026 replaces it with a fresh design ("restart-from-here": new run at target sha, source untouched) that uses only APIs agent-server documents. The `commit_sha_at_time_of_event` addition to event-normalize survives unchanged. Original decision text preserved below for historical record.

---

# ADR-025 — Restore via fork, not in-place `git reset` + conversation-state rewind (Stage 6.4b · Stage 6.4c)

**Status:** Superseded by ADR-026 (2026-08-06 07:55 EDT). Previously: Proposed
**Date:** 2026-08-06
**Slice:** Stage 6.4b (per-run worktrees) enables · Stage 6.4c (restore action) consumes
**Related:**
- [`docs/reconciliation-plan-v1.md`](../reconciliation-plan-v1.md) §6.4 (canonical plan text that this ADR amends by evidence)
- [`docs/reconciliation-plan-stage-6.md`](../reconciliation-plan-stage-6.md) §6.4.1–6.4.5 (spec block that this ADR supersedes at the design level)
- BUILD_LOG.md 2026-08-06 06:53 EDT (Stage 6.4 fork-from-here CLOSED — restore/revert deferred to 6.4b + 6.4c)
- ADR-016 (Colossus↔GitHub parity — every run-worktree file must be either tracked or ignored)

**Supersedes:** —
**Superseded by:** [ADR-026](./026-restart-from-here.md)

## Context

`docs/reconciliation-plan-v1.md` §6.4 and `docs/reconciliation-plan-stage-6.md` §6.4.1–§6.4.5 specify a "checkpoint-to-disk revert" whose backend calls `git reset --hard <checkpoint.commit_sha>` in the run's working directory **in place**, then calls a `restore_conversation_state(run_id, checkpoint_id)` helper to rewind the agent's conversation state. The `Forge-OH-reconciliation-plan-v1-stage-6.md` block warns that `workdir` must be genuinely per-run before the reset and asks the implementer to confirm the exact lookup / restore function names during 6.4.1 inspection.

A codebase inspection on 2026-08-06 (recorded in DEBUG_LOG.md) found that **none of §6.4's four load-bearing prerequisites exist**:

1. **No `Checkpoint` entity.** No SQLite table, no ID, no persisted association between a git commit SHA and an event. What the plan calls a "checkpoint" is materialised only as "user-message events in the timeline" (spec D2 language, cf. `src/app/(dashboard)/runs/[runId]/page.tsx:366`). There is no `get_checkpoint_metadata`.
2. **No per-run worktrees.** `bff/routers/runs.py:167–184, 332–343` resolves `working_dir` from the run's `workspaceId` via agent-server's workspace list, or falls back to `_WORKSPACE_ROOT / "pending"`. Two concurrent runs against the same `workspaceId` share the same physical directory. There is no `WORKTREE_ROOT`, no `git worktree add`, no `get_run_workdir`.
3. **No conversation-state restore.** `openhands-sdk==1.40.0` exposes `Conversation.fork()` (creates a new conversation) but does **not** expose "rewind this conversation to event N in place." There is no `restore_conversation_state` we can call.
4. **No safety guard.** The plan's `workdir.startswith(str(WORKTREE_ROOT))` guard presumes worktrees exist. It cannot be sound today because every path Bff resolves is `_WORKSPACE_ROOT / <workspace path>` — outside any worktree root, by construction.

The plan's §6.4 line 243 hints at the correct composition:

> Frontend: revert control on the checkpoint/history view, **composed with the existing `Conversation.fork()` mechanism**.

Stage 6.4 shipped that mechanism (fork-from-here on user-message events) as a **non-destructive** operation: the original run is preserved; a new run branches off at the selected event. This ADR takes the compose-with-fork hint literally and rejects the in-place destructive framing.

## Decision

**Restore is implemented as fork + worktree reset, not as in-place `git reset --hard` + in-place conversation-state rewind.**

Concretely:

- **Stage 6.4b — Per-run worktrees.**
  Every run gets its own git worktree under a configurable `WORKTREE_ROOT` (default `~/.forge-oh/worktrees/`). Provisioning runs at run start via `git worktree add ${WORKTREE_ROOT}/<run_id> <base_ref>` against the workspace's git repo. Teardown at run deletion via `git worktree remove`. `bff/routers/runs.py`, `bff/services/event_relay.py`, `bff/services/run_compare.py`, and `bff/services/metrics_aggregation.py` all route through the per-run worktree path instead of the shared `workspace.working_dir`.

- **Stage 6.4c — Restore via fork.**
  New endpoint `POST /api/runs/{run_id}/restore` with body `{from_event_id}`:
  1. Look up the git commit SHA associated with `from_event_id` (recorded on user-message events by a small `event_normalize.py` addition — `commit_sha_at_time_of_event`).
  2. Call the existing `POST /api/conversations/{run_id}/fork` upstream path with `{from_event_id}` to create the branched conversation (this is the same call fork-from-here uses today).
  3. In the **new fork's** freshly-provisioned worktree (Stage 6.4b), run `git reset --hard <sha>`. The `WORKTREE_ROOT` guard is now trivially sound because worktrees are the only paths `git worktree add` produces.
  4. Return `{ok, restored_run_id, from_event_id, reset_to_sha}`.
  5. The original run is **untouched**: its worktree, conversation state, and event history all persist.

**Frontend:** `RestoreToHereButton` mirrors `ForkFromHereButton` on user-message events, with a confirmation dialog stating: *"Creates a new run at this point with files reset to that state. Your current run is preserved."*

## Rationale

**Composes with existing shipped primitives.** `Conversation.fork()` is already wired end-to-end (BFF fork endpoint 38/38 tests, `ForkFromHereButton` vitest 10/10, Playwright DoD 1/1, all landed in Stage 6.4). Adding a `git reset --hard` inside the new fork's isolated worktree is one endpoint delta and one UI button.

**P1 (checkpoint entity) and P3 (conversation-state restore) evaporate as separate problems.** User-message events are the anchors; the new addition is a single `commit_sha_at_time_of_event` field on those events during normalisation. Conversation state at `from_event_id` is delivered by SDK fork semantics — no in-place rewind API is required from `openhands-sdk`.

**Safety guard becomes sound by construction.** With worktrees as the only per-run FS surface, `path.startswith(WORKTREE_ROOT)` is a real invariant, not a hopeful assertion. A bug in path resolution now fails safely (rejects the reset) instead of silently wiping a shared workspace.

**Non-destructive matches the rest of the system's posture.** Forge-OH ships append-only BUILD_LOG and DEBUG_LOG, treats user-message events as durable anchors, and preserves prior state on fork. In-place destructive revert would be the only "wipe prior state" primitive in an otherwise append-only system. Restore-via-fork preserves that invariant.

**Idempotency ledger (Stage 6.3) stays trivially correct.** A restored run is a *new* run — the idempotency ledger keyed on `(task_id, step_index, argument_hash)` (`docs/reconciliation-plan-v1.md` §6.3) doesn't have to reason about "which prior records should be invalidated when the run is rewound." Nothing gets invalidated because nothing is rewound; a new run just starts populating its own records.

**Unblocks concurrency (Stage 2.4).** The plan §2.4 explicitly plans for bounded concurrent worktree-agents. That is impossible today because runs share a physical workspace directory. 6.4b's per-run worktrees are the concrete foundation §2.4 needs.

**Aligns with the reconciliation plan's own hint.** §6.4 line 243 already calls for composing with `Conversation.fork()`. This ADR takes that literally.

## Alternatives considered

### Alt A · Literal spec (in-place `git reset --hard` + in-place `restore_conversation_state`)

Rejected. Three concrete blockers:

- **Requires an SDK feature that does not exist.** `openhands-sdk==1.40.0` has no in-place conversation-state rewind API. Building one means either forking the SDK (Kosmos-scale port; violates single-user local-first scope) or authoring a bespoke snapshot table on top of agent-server's event log (large, load-bearing, orthogonal to the actual user-visible feature).
- **Destructive semantics with a shared-path failure mode.** One bug in path resolution → user's actual workspace wiped. Even with the `WORKTREE_ROOT` guard, the invariant is externally-asserted, not structurally guaranteed.
- **Destroys prior state.** Runs the user may want to return to later are gone. Breaks the append-only invariant the rest of the system holds.

### Alt B · In-place reset + snapshot-and-replay conversation state

Author our own event-log snapshot table (rows keyed by `(run_id, event_id)`, storing conversation-state pickle-or-JSON), rewind via truncation + reload. Rejected on cost/benefit: significant new persistence surface, requires deciding what "conversation state" is exhaustively (message history, plan state, tool-result cache, security-analyzer state, memory-adapter reads, …), and the user-visible outcome is identical to restore-via-fork except the original run is destroyed.

### Alt C · Never revert; users copy-paste and restart

Rejected. Contradicts plan §6.4's stated goal of composed conversation+FS restore, and forfeits the D3 file-level restore that the user has repeatedly asked for.

## Consequences

**Positive**

- Non-destructive: original run always preserved.
- Composes with fork; no new "big" primitive.
- Enables concurrent runs against the same workspace (Stage 2.4) as a byproduct.
- Safety guard is a real structural invariant.
- P1 + P3 collapse into a single `commit_sha_at_time_of_event` field on user-message events during 6.4c.

**Negative**

- Every restore creates a new run. The runs list will grow. Acceptable for single-user; if that ever changes, add a runs-list GC or "hide restore-parents" filter. Filed as future work in the stage-6 companion doc.
- Per-run worktrees add filesystem sprawl under `WORKTREE_ROOT`. Bounded by a GC-on-run-deletion policy in 6.4b; explicit user action to purge available via `git worktree prune` on runs the user has deleted.
- The plan's §6.4 spec block (destructive revert) is now historical prose. It stays in `docs/reconciliation-plan-stage-6.md` verbatim, but the stage-6 companion gets a superseded-by header pointing to this ADR.

**Neutral / follow-ups**

- `event_normalize.py` needs a `commit_sha_at_time_of_event` field on user-message events. Landed in 6.4c.
- `bff/services/run_compare.py` (already worktree-path-aware in structure) becomes stronger because both sides of the compare are guaranteed-isolated worktrees.
- If the SDK later exposes a genuine in-place rewind, this ADR can be amended (not superseded) to add a `destructive: true` mode on `/api/runs/{run_id}/restore`. Default stays non-destructive.

## Contingency triggers

Amend this ADR if any of:

- `openhands-sdk` introduces a first-class in-place conversation-state rewind API (would reopen Alt B as a real option).
- `WORKTREE_ROOT` filesystem sprawl becomes a real operational pain (would trigger a shared-checkout + per-run branch alternative, not a return to Alt A).
- Concurrency assumptions from §2.4 shift (single-user → multi-user; explicitly out-of-scope today).
