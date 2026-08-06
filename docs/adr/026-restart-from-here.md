# ADR-026 — Restart-from-here (fresh run at target file state, not fork-and-reset)

**Status:** Proposed
**Date:** 2026-08-06
**Slice:** Stage 6.4c (supersedes ADR-025 mid-implementation)
**Related:**
- [ADR-025](./025-restore-via-fork.md) — the design this replaces
- [`docs/reconciliation-plan-v1.md`](../reconciliation-plan-v1.md) §6.4 (canonical plan text)
- [`docs/reconciliation-plan-stage-6.md`](../reconciliation-plan-stage-6.md) §6.4.1–6.4.5 (spec block)
- BUILD_LOG.md 2026-08-06 07:52 EDT (fork-inheritance probe VERDICT=inherited)
- BUILD_LOG.md 2026-08-06 07:54 EDT (mutation probe VERDICT=immutable)
- ADR-016 (Colossus↔GitHub parity — every run-worktree file tracked or ignored)

**Supersedes:** [ADR-025](./025-restore-via-fork.md) (design premise invalidated by evidence probes)
**Superseded by:** —

## Context

ADR-025 (proposed 2026-08-06 06:59 EDT) specified that "restore to here" would be implemented as `Conversation.fork()` + `git reset --hard <sha>` inside the **fork's** freshly-provisioned worktree, keyed off a `commit_sha_at_time_of_event` field on user-message events. That design assumed two things about agent-server 1.40.0 that turned out to be false:

1. **Assumption A** (rejected): forks get a fresh `workspace.working_dir`. Two hours after ADR-025 was drafted, `scripts/6-4c-fork-worktree-probe.sh` created a parent run, forked it, and read both `working_dir` fields from agent-server. Both pointed at the same path: the parent's per-run worktree (`~/.forge-oh/worktrees/run-<hex>`). Verdict: **fork inherits parent's worktree**. A `git reset --hard` in "the fork's worktree" would destroy the parent's files — the exact shared-path failure mode ADR-025 was written to prevent.

2. **Assumption B** (rejected): even if fork inherits, we can PATCH the fork's `working_dir` to point at a fresh worktree. `scripts/6-4c-patch-schema-inspect.sh` fetched agent-server 1.40.0's OpenAPI spec and inspected the `UpdateConversationRequest` schema for `PATCH /api/conversations/{conversation_id}`. It exposes only `title` and `tags`. Nothing workspace-shaped. A PATCH with `{workspace: {working_dir: ...}}` returns `200 {"success":true}` while silently discarding the field. Verdict: **working_dir is immutable post-creation**.

There is no possible amendment to ADR-025 that keeps its architectural premise sound against agent-server 1.40.0's actual surface. The fork endpoint clones the parent's workspace verbatim, and no endpoint lets us change it afterwards.

Options considered (design space enumerated in the session that authored this ADR):

- **A · Restart-from-here** — `POST /api/runs/{run_id}/restart` creates a NEW run with a fresh worktree checked out at `<commit_sha_at_time_of_event>`, seeded with the user-message text from `from_event_id` as the initial prompt. Loses conversation state (tool-call history, plan state, prior assistant messages).
- **B · Destructive in-place reset** — `git reset --hard <sha>` in the parent's own worktree. Preserves conversation state; destroys prior file state permanently; breaks the append-only invariant the rest of the system holds. ADR-025 explicitly rejected this as "Alt A" four hours earlier for the same reasons that still apply.
- **C · Park 6.4c indefinitely** — wait for agent-server to expose a workspace mutation API. Blocks stage-6 progression on an upstream we do not control.

## Decision

**Restore is renamed "restart" and implemented as a fresh run against a fresh worktree checked out at the target event's commit SHA.**

Concretely:

- **New endpoint: `POST /api/runs/{run_id}/restart`** with body `{from_event_id: str}`.
  1. Look up the source run's conversation on agent-server. Extract the `workspace.working_dir` and, from it, the **source repo path** (the git worktree's source, resolved via `_resolve_source_repo_for_worktree` in `bff/services/worktree.py`).
  2. Look up the event by `from_event_id`. Verify it is a user-message event. Extract:
     - `commit_sha_at_time_of_event` — new field, populated on normalisation (see below).
     - The user's message text (via existing `event_normalize._message_summary` reachable content).
  3. Mint a new `run_id` (`run-<hex12>`) and call `provision_worktree(new_run_id, source_repo, base_ref=<commit_sha_at_time_of_event>)`. Because `git worktree add <path> <ref>` accepts any ref, the new worktree lands at exactly the target file state.
  4. Call the existing `POST /api/conversations` (same code path as `POST /api/runs`) with the fresh worktree as `workspace.working_dir` and the extracted user-message text as `initial_message.content`.
  5. Return `{ok, restarted_run_id, from_event_id, reset_to_sha, source_run_id}`.
  6. Rollback: if step 4 fails, `remove_worktree(new_run_id, missing_ok=True)`. The source run is never touched.

- **Event-normalize addition:** `commit_sha_at_time_of_event` on user-message events in `bff/services/event_normalize.py`. Value captured at ingest time as the current HEAD SHA of the run's worktree when the user-message event is normalised. Not backfilled onto pre-existing events; those simply cannot be restart-anchors (front end will hide the button when the field is missing).

- **Frontend contract:** `RestartFromHereButton` mirrors `ForkFromHereButton` on user-message events with `commit_sha_at_time_of_event` set. Confirmation dialog copy: *"Start a new run at this point with files reset to that state. You'll re-send your original message; the assistant's prior replies won't carry over. Your current run is preserved."* Feature-flagged under the same `NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED` flag as fork-from-here.

- **Runs-list treatment:** restarted runs appear as normal top-level runs. They carry a `source_run_id` field in their metadata (recorded in the BFF `tags` field via `PATCH /api/conversations/{id}` with `{"tags": {"restarted_from": "<source_run_id>", "restarted_at_event": "<from_event_id>"}}` — this uses the ONE PATCH field agent-server DOES accept). No parent/child collapsing in the runs list; that's deferred to a later slice consistent with the locked-in-then-broken Q2 decision.

## Rationale

**Only viable option that preserves system invariants.** Options B (in-place reset) and C (park) both violate an invariant Forge-OH ships today:

- B violates append-only file history and reintroduces the shared-path failure mode ADR-025 rejected.
- C blocks progression on an upstream we don't control.

A is the only option that keeps: append-only files, structural isolation, source run untouched, no dependency on unshipped agent-server APIs.

**Uses only APIs agent-server 1.40.0 actually exposes.** `POST /api/conversations`, `POST /api/conversations/{id}/events` (via BFF ingestion), and `PATCH /api/conversations/{id}` with `tags` are all documented and verified. No hopeful API assumptions.

**The `commit_sha_at_time_of_event` work is preserved from ADR-025.** The event-normalize addition is unchanged — it was always going to be the anchor. Only the composition on top of it changes.

**Loss of conversation state is honest, bounded, and named.** Fork-from-here (shipped in Stage 6.4) already preserves conversation state at the picked event. Users who want that keep using it. Restart-from-here fills the different, real gap: "I want to actually rewind the files, not the conversation." The UI copy makes the tradeoff visible; the rename ("Restart" not "Restore") makes it structural.

**`git worktree add <path> <ref>` accepts any ref.** This is the key primitive that makes A work at all: we do not need agent-server to mutate a working_dir because we never fork the conversation — we create a fresh one, and its worktree lands at the target sha by construction.

**Non-destructive matches the rest of the system's posture.** Fork-from-here, BUILD_LOG, DEBUG_LOG are all append-only. Restart-from-here preserves the source run's worktree, conversation, and events untouched.

## Alternatives considered

### Alt A · ADR-025 as originally written

Rejected on evidence. Two probes (2026-08-06 07:50 EDT and 07:54 EDT) invalidated its two load-bearing premises. Included here for completeness only.

### Alt B · Destructive in-place `git reset --hard` in the source run's worktree

Rejected on the same grounds ADR-025 rejected it as "Alt A" (see ADR-025 §Alternatives): destroys prior file state, breaks append-only invariant, single-path-resolution-bug failure mode destroys shared workspace. The immutability of agent-server's workspace field is a new blocker on top of the old rejection.

### Alt C · Author snapshot-and-replay conversation state ourselves

Would preserve conversation state by authoring an event-log snapshot table (rows keyed by `(run_id, event_id)`, storing conversation-state serialised) and rewinding via truncation + reload. Rejected on the same grounds ADR-025 rejected it as "Alt B": significant new persistence surface, requires exhaustive definition of "conversation state," and the user-visible outcome is identical to restart-from-here except at 10× the implementation cost.

### Alt D · Fork the agent-server SDK to add working_dir mutation

Explicit non-goal per project instructions: single-user local-first, no fork of upstream unless the user asks. Would also violate the "if uncertain, stop and ask" rule mid-slice.

### Alt E · Wait for agent-server upstream

Considered as Option C above. Rejected because it indefinitely blocks Stage 6.4c on an upstream Forge-OH does not control, and the semantic outcome of restart-from-here is what the reconciliation plan §6.4 actually asks for (files at a prior point in time) once the "in-place" adjective is dropped.

## Consequences

**New files:**
- `bff/routers/runs.py` — new `POST /runs/{run_id}/restart` handler.
- `bff/services/restart.py` — restart composition (worktree + fresh conversation + rollback).
- `bff/tests/test_restart_endpoint.py` — 8+ tests covering happy path, missing sha, missing event, worktree provision failure, agent-server create failure, non-user-message anchor rejection, source-run-not-found, cross-workspace guard.
- `bff/tests/test_event_normalize_commit_sha.py` — tests for the new field on user-message events.
- `src/components/events/RestartFromHereButton.tsx` — feature-flagged UI button.
- `src/tests/RestartFromHereButton.test.tsx` — vitest coverage.

**Modified files:**
- `bff/services/event_normalize.py` — new `commit_sha_at_time_of_event` field on user-message events.
- `bff/routers/runs.py` — new endpoint import, feature-flag wire-up.
- `docs/reconciliation-plan-stage-6.md` — supersede §6.4.1–6.4.5 design layer with reference to this ADR. Plan text stays as historical prose per the same convention ADR-025 used.

**No changes to:**
- `bff/services/worktree.py` — `provision_worktree` already accepts a `base_ref` argument that supports the target-sha use case.
- Fork-from-here (Stage 6.4 shipped). Restart is an orthogonal primitive; fork stays unchanged.

**PORTING_LEDGER:** no ports added or removed. This is composition of shipped primitives + one new endpoint.

**Downstream ADRs:**
- ADR-016 (Colossus↔GitHub parity) reaffirmed: the new worktree, like every other run worktree, is subject to the same "every file tracked or ignored" invariant.
- ADR-025 status updated to `Superseded by ADR-026` via a status-amendment block prepended above its front matter.

## Lock-in phase

Stage 6.4c. This ADR is `Proposed` until the restart endpoint ships green tests and the frontend button lands. It becomes `Ratified` when both ship in the same commit per the governing rule.

## References

- `docs/reconciliation-plan-v1.md` §6.4 (canonical plan)
- `docs/reconciliation-plan-stage-6.md` §6.4.1–6.4.5 (spec block, superseded by this ADR at design layer)
- ADR-025 (superseded predecessor)
- BUILD_LOG.md 2026-08-06 07:52 EDT (fork-inheritance probe)
- BUILD_LOG.md 2026-08-06 07:54 EDT (workspace mutation probe)
- `scripts/6-4c-fork-worktree-probe.sh` (evidence artifact)
- `scripts/6-4c-agent-server-mutation-probe.sh` (evidence artifact)
- `scripts/6-4c-patch-schema-inspect.sh` (evidence artifact)
