> **STATUS AMENDMENT (2026-08-06 09:21 EDT):** Ratified.  Backend endpoint
> ``POST /api/runs/{run_id}/restart`` shipped and green in `bff/tests/`
> (45/45 pytest at commit `7fc5fb1`).  BFF-side sha capture via
> ``event_normalize.py`` §6.4c gate + ``bff/services/event_commit_ledger.py``
> verified live on Colossus (`stage-6.4c-verify.sh` all-green,
> 2026-08-06 09:13 EDT).  Frontend ``RestartFromHereButton`` shipped with
> ADR-026 §Frontend contract normative copy verbatim, sha-presence gate
> enforced, and rules-of-hooks compliance restored.  Unit vitest covers
> the copy-guard and the sha-gate; Playwright e2e
> ``src/tests/e2e/run-restart-from-here.spec.ts`` proves
> ``{from_event_id: ...}`` wire body verbatim and negatively asserts the
> assistant-event + missing-sha D2 cases.  ADR-025 remains Superseded.
>
> Note: the ``ForkFromHereButton`` shares the same rules-of-hooks bug
> pattern (``useCallback`` after early return).  Not fixed in this slice
> — out of scope; tracked as a follow-up.

# ADR-026 — Restart-from-here (fresh run at target file state, not fork-and-reset)

**Status:** Ratified
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

- **Storage of `commit_sha_at_time_of_event`:** BFF-side sidecar table (option W2 below). User-message events are created by agent-server, not by the BFF, so the sha cannot be stored on the event itself without forking agent-server. Instead, the BFF captures the run-worktree's current HEAD sha at the moment it hands the message text to agent-server, and persists the mapping `(run_id, event_id) → commit_sha` in a small aiosqlite table. Event-normalize joins the sidecar on the way out so the frontend sees `commit_sha_at_time_of_event` on the event object exactly as if agent-server had produced it. Fully documented in the Storage section below.

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
- `bff/services/event_commit_ledger.py` — W2 storage module (aiosqlite pattern from `idempotency_ledger.py`).
- `bff/services/restart.py` — restart composition (worktree + fresh conversation + rollback).
- `bff/tests/test_event_commit_ledger.py` — insert/fetch/delete + schema tests.
- `bff/tests/test_event_normalize_commit_sha.py` — normaliser stamps `commit_sha_at_time_of_event` when the sidecar has a hit.
- `bff/tests/test_restart_endpoint.py` — 8+ tests covering happy path, missing sha, missing event, worktree provision failure, agent-server create failure, non-user-message anchor rejection, source-run-not-found, cross-workspace guard.
- `src/components/events/RestartFromHereButton.tsx` — feature-flagged UI button.
- `src/tests/RestartFromHereButton.test.tsx` — vitest coverage.

**Modified files:**
- `bff/main.py` — register `event_commit_ledger.init_db` / `close_db` in the FastAPI lifespan.
- `bff/services/event_normalize.py` — optional `sha_lookup` kwarg on `normalize_event`/`normalize_events`; stamps `commit_sha_at_time_of_event` on user MessageEvents when the lookup returns a value.
- `bff/routers/runs.py` — (a) capture sha after `create_run` initial-message, (b) capture sha after `send_run_message`, (c) new `POST /runs/{run_id}/restart` handler, (d) cascade delete via `event_commit_ledger.delete_run` in `DELETE /runs/{id}`, (e) pass `sha_lookup` into normalisation on the events read paths.
- `docs/reconciliation-plan-stage-6.md` — supersede §6.4.1–6.4.5 design layer with reference to this ADR. Plan text stays as historical prose per the same convention ADR-025 used.

**No changes to:**
- `bff/services/worktree.py` — `provision_worktree` already accepts a `base_ref` argument that supports the target-sha use case.
- Fork-from-here (Stage 6.4 shipped). Restart is an orthogonal primitive; fork stays unchanged.
- Agent-server (no fork; only APIs it documents are used).

## Storage of `commit_sha_at_time_of_event`

User-message events are created by agent-server (`POST /api/conversations` with `initial_message` for the first message, `POST /api/conversations/{id}/events` with `role=user` for subsequent messages). The BFF never authors the event body itself, so it cannot stamp a new field onto it. Four options were considered:

- **W1 — fork agent-server** to add `commit_sha_at_time_of_event` as a first-class field on `MessageEvent`. Rejected: forking upstream is an explicit non-goal per project instructions unless the user asks; this ADR asks only for what agent-server 1.40.0 already exposes.
- **W2 — BFF sidecar table (accepted)** — details below.
- **W3 — reflog reconstruction** at restart time (walk `git reflog` in the worktree, correlate to event timestamp). Rejected: reflogs are not durable (git gc), agent-server bash tools can move HEAD between message and observation, timestamp-→-sha correlation is racy across concurrent runs.
- **W4 — use current HEAD at restart-invocation time** (ignore per-event sha). Rejected: reduces "restart from this specific message" to "restart with whatever the files look like right now," which collapses every restart button on the same run to the same outcome and defeats the reconciliation-plan §6.4 intent.

### W2 decision

A new aiosqlite-backed table lives in the BFF, following the pattern established by `bff/services/idempotency_ledger.py` (aiosqlite + `init_db(app)` / `close_db(app)` in the FastAPI lifespan; single shared connection on `app.state`).

**Module:** `bff/services/event_commit_ledger.py`

**Table schema:**

```sql
CREATE TABLE IF NOT EXISTS event_commit_shas (
  run_id       TEXT NOT NULL,
  event_id     TEXT NOT NULL,
  commit_sha   TEXT NOT NULL,
  captured_at  REAL NOT NULL,
  PRIMARY KEY (run_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_evshas_run ON event_commit_shas (run_id);
```

**Capture points (both must land before ADR-026 is Ratified):**

1. **First user message on a run** — in `bff/routers/runs.py` `create_run` handler, after `POST /api/conversations` returns the new conversation payload, the BFF already knows: (a) the fresh worktree path (from `provision_worktree`), and (b) the `event_id` of the freshly-created `initial_message` event (returned by agent-server in `conversation.events[0].id` or reachable via a follow-up `GET /api/conversations/{id}/events?limit=1`). BFF captures `git rev-parse HEAD` inside the worktree and inserts one row. First-message capture happens after conversation creation succeeds; failure to capture is logged but does NOT fail the run creation (frontend simply hides the restart button on that event).

2. **Send-while-running user message** — in `bff/routers/runs.py` `send_run_message` handler, after `POST /api/conversations/{id}/events` returns, BFF reads the returned `event.id` (agent-server returns the created event), captures `git rev-parse HEAD` in the run's worktree, inserts one row. Same failure semantics.

**Read path:** `event_normalize.normalize_event(raw, *, sha_lookup=None)` gets a new optional keyword parameter. When `raw.kind == "MessageEvent"` and `_message_summary` recognises the source as user (existing helper), the normaliser calls `sha_lookup(event_id) -> Optional[str]` and stamps `commit_sha_at_time_of_event` on the output dict when the lookup returns a hit. Absent hits mean the event predates ADR-026 or the capture failed — both cases downgrade gracefully (the frontend hides the button).

**Cleanup:** rows are deleted lazily by a `delete_run(run_id)` helper called from the existing `DELETE /api/runs/{run_id}` code path in `bff/routers/runs.py`. No TTL / no daemon.

**Migration:** the `init_db(app)` call in `bff/main.py`'s lifespan handler runs `CREATE TABLE IF NOT EXISTS` on startup; no manual migration step. Existing runs simply have zero rows in the new table and their user-message events never expose `commit_sha_at_time_of_event`, matching the graceful-downgrade contract above.

**Test coverage (added in this slice):** `bff/tests/test_event_commit_ledger.py` — insert-and-fetch, primary-key uniqueness, index existence, `delete_run` cascade. `bff/tests/test_event_normalize_commit_sha.py` — normaliser stamps the field when `sha_lookup` returns a value, omits it when absent, ignores non-user MessageEvents.

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
