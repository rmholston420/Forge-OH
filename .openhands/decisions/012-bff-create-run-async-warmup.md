# ADR-012 — BFF /api/runs should not block on agent-server LLM warmup

**Status:** Proposed
**Lock-in phase:** Slice G.1 follow-up (post-nightly-harness).
**Supersedes:** —

## Context

The self-eval harness (`openhands_tools_ext/selfeval/harness.py`)
submits tasks via `POST /api/runs` against the BFF, then polls
`GET /api/runs/{id}` for terminal status.

On the first live cycle after slice G.1 landed
(`docs/selfeval/2026-08-04-selfeval.json`, cycle at 22:37 EDT), every
task returned `error / transport error (ReadTimeout)` at exactly 30.0s.
Investigation showed the BFF **did** return `200 OK` for each POST
(`.forge-logs/bff.log` lines 2495, 2502, 2529, 2531, 2543) — the client
had already hung up.

Root cause: `bff/routers/runs.py::create_run()` awaits a synchronous
`POST /api/conversations` to agent-server (`bff/openhands_client.py`
uses `httpx.Timeout(60.0)`). Agent-server's conversation constructor
initializes an LLM client, which (when vLLM :8501 is unreachable, as
during the 22:37 cycle) can consume a large fraction of that 60s
window. The harness's 30s cap could not span the BFF's legitimate wait.

The fast fix (this slice) bumped the harness cap to 90s. That masks
the underlying blocking behavior but does not fix it.

## Decision

**Proposed:** Refactor `bff/routers/runs.py::create_run` so that
`POST /api/runs` returns as soon as it has:

1. Resolved routing + preset + workspace (fast, all local),
2. Created the empty conversation on agent-server (or has scheduled it
   to be created in the background), and
3. Emitted the initial `RunCreated` event to Socket.IO so the frontend
   can display "starting".

Any LLM warmup, first-turn dispatch, or sync agent-server calls that
depend on model availability move into a background task
(FastAPI `BackgroundTasks` or an explicit `asyncio.create_task`), with
failures surfaced via the WS event stream (`run.error` payloads) instead
of the create-run response body.

Result: the harness POST completes in <2s regardless of model state,
and the harness client-side timeout can drop back to ≤10s.

## Rationale

- **Symptom-timeout is a smell.** The current 90s cap is defensive
  against a design flaw, not a business constraint.
- **Front-end already handles streaming via Socket.IO.** The GUI does
  not depend on `/api/runs` returning fully-populated run state — it
  subscribes to the WS channel and hydrates from events.
- **Alignment with F.19 model swap contract.** Model warmup is a
  fallible operation that must not block the API surface.
- **Alternatives considered:**
  1. Keep the sync path + a bigger timeout: still fragile once we add
     larger models with longer warmup (Qwen3.6-35b-nvfp4 first-token
     latency on cold load).
  2. Have the harness poll from the point of POST accept: works but
     doesn't help the GUI's cold-start UX, and duplicates work.

## Consequences

**Files to change:**
- `bff/routers/runs.py` — split `create_run` into sync setup + async
  continuation; wire agent-server call as `BackgroundTasks`.
- `bff/tests/test_runs_router.py` — assert POST returns before any
  slow inner call; assert failure of the inner call surfaces via WS
  event, not via HTTP.
- `openhands_tools_ext/selfeval/harness.py` — drop the 90s cap back
  to ≤10s once the BFF change lands; delete the `test_post_runs_timeout_at_least_90s` regression once the invariant flips.
- `SESSION_HANDOFF.md` — note the ADR-012 follow-up as the next slice
  after G.1's DoD is met.

**Ports/adapters affected:** BFF → agent-server (async instead of sync
inside the request), BFF → frontend (adds `run.warming_up` and
`run.warmup_failed` WS events).

## Lock-in phase

To be implemented in the first slice after G.1 signs off with a green
live cycle. Not required to close G.1.

## References

- `.forge-logs/bff.log` lines 2495–2543 (successful 200 OK for cycle
  the harness gave up on).
- `bff/openhands_client.py` line 26 (`httpx.Timeout(60.0)`).
- `openhands_tools_ext/selfeval/harness.py` line 141 (temporary 90s cap).
- `docs/selfeval/2026-08-04-selfeval.json` (first failing cycle).
- BUILD_LOG entry `2026-08-03 22:55 EDT`.
