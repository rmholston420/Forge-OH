# ADR-007: Execution-Verified Self-Debugging Loop

- **Status:** Accepted
- **Date:** 2026-08-03
- **Slice:** E (Recommendation #2, Forge-OH-Action-Plan-v4)
- **Related:** [PORTING_LEDGER.md](../../PORTING_LEDGER.md) entry #2 (LDB); ADR-006 (RepoGraph, Rec #1).

## Context

Before Slice E, the agent could edit code, run bash, and stop when its
LLM felt "done" — with no automatic check that the edits it just made
actually pass the project's tests. In practice this means a debugging
task frequently ends with the agent believing it fixed the bug while
CI (or the human user) discovers the tests are still red. LDB (Zhong
et al., 2024, arXiv:2402.16906) shows that an LLM given per-block
runtime state and forced to retry until execution passes converges on
real fixes far more often than one asked to reason from static code
alone.

Rec #2 in the plan calls for a bounded self-debugging loop: after
every stop attempt, run the test suite; if it fails, feed the agent
the failure and let it try again, up to a fixed budget.

## Decision

### 1. Event shape: existing rails, no new endpoints

Verify iterations are emitted into the run's event stream as standard
`ActionEvent` → `ObservationEvent` pairs with `tool_name="verify_step"`.
The existing BFF read path (`bff/services/trace_reconstruction.py`)
maps `verify_step` to a new span kind `verify` via `_KIND_MAP`. That
is the only BFF change. There are:

- Zero new REST endpoints.
- Zero new database tables.
- Zero changes to the frontend fetch layer.

The frontend picks up verify spans through the same
`useTraceSpans(runId)` hook it already uses for everything else. A
dedicated `VerifyStepCard` renders when a span's `kind === "verify"`.

### 2. Hook point: OpenHands SDK `HookEventType.STOP`

The retry policy runs as a `HookType.COMMAND` STOP hook against the
OpenHands SDK's existing hook manager (`openhands.sdk.hooks.manager`).
When the agent tries to finish, the SDK invokes the hook, our shim
runs one verification, and returns `decision="block"` if a retry is
required. Exit-code semantics follow Claude Code's hook contract as
echoed in `openhands.sdk.hooks.executor.HookResult`:

- Exit 0 with `{"decision": "block", …}` on stdout → agent must retry.
- Exit 0 with `{}` (no decision) → agent may stop.
- Exit 2 → hard block (reserved for infrastructure failure).

### 3. Plugin layout: `openhands_tools_ext/verify/` sibling to RepoGraph

Five modules mirror the five DoD steps in the plan:

| Module | Slice | Purpose |
| --- | --- | --- |
| `schema.py` | E.1 | `VerificationStep` Pydantic model + Zod parity in `src/lib/schemas/verify.ts` |
| `selector.py` | E.2 | `detect_runner()` + `select_targets()` + `build_command()` |
| `runner.py` | E.2 | `run_verification()` subprocess wrapper, returns `VerificationStep` |
| `breakpoint/inspector.py` | E.3 | LDB-inspired runtime state inspector |
| `loop.py` | E.4 | `VerifyLoop` retry policy |
| `hook.py` | E.4 | CLI shim runnable as `python -m openhands_tools_ext.verify.hook` |

The frontend touches only two new files:
`src/components/domain/VerifyStepCard.tsx` and
`src/components/domain/VerifyIterationsWidget.tsx`, plus a two-line
edit each to `SpanRow.tsx` and `MetricsTab.tsx`.

### 4. Runner selection precedence

`detect_runner()` prefers Python over JS/TS because Forge-OH is a
polyglot repo: the backend suite is faster and catches wider
regressions than the frontend suite in almost every case. Precedence
is:

1. `pyproject.toml` present → `pytest`.
2. `vitest.config.*` present → `vitest`.
3. `jest.config.*` present → `jest`.
4. `package.json` with a `scripts.test` present → `npm test`.
5. Otherwise → skip verification.

Users can override with `runner_override` on `run_verification`.

### 5. Selection strategy: nearest-test, not full-suite

`select_targets()` runs the narrowest test that covers each edited
file, in this order per file:

1. The file itself if it is already a test (`test_*.py`, `*.test.ts`,
   etc.).
2. A sibling test file with the same base name.
3. The nearest ancestor directory that contains any tests (dir-level
   fallback).

This is the "narrowest target" invariant from the plan. Full-suite
runs are avoided because on Forge-OH's own repo the backend suite is
~500 tests; running it three times per STOP would burn ~5s × 3 =
~15s per finish attempt for a single-file bugfix.

### 6. State persistence across STOP invocations

Each STOP hook invocation is a fresh subprocess. Retry state
(iterations used, edited-file set, last verdict) is kept in
`$OPENHANDS_PROJECT_DIR/.forge-oh/verify-state.json` keyed by session
id. Multiple concurrent sessions on the same workspace do not
interfere. The state file is small (a few kilobytes) and can be
deleted at will — losing it just resets the retry counter.

### 7. LDB port: reference-only

We reviewed `FloridSleeves/LLMDebugger` @ `49ac191f` and vendored
**none** of its Python code. The runtime inspector at
`openhands_tools_ext/verify/breakpoint/inspector.py` is a fresh 200-LOC
implementation using `sys.settrace` + `runpy.run_path`, adopting only
LDB's *pattern* (record `frame.f_locals` at each hit, render as
`[order] file:line  k=v; k=v; …`). Reasons in PORTING_LEDGER.md entry
#2. TL;DR: upstream is a CLI benchmark harness with hard-coded
`.tmp.py` paths, an `astroid` dependency, a 700-LOC vendored
control-flow-graph builder, and interactive-loop `pdb.Pdb` tracing —
none of which fit our sandbox model.

### 8. Bounded budget: default 3

Max iterations defaults to 3 (`DEFAULT_MAX_ITERATIONS` in
`openhands_tools_ext/verify/loop.py`). Overridable per run via
`FORGE_OH_VERIFY_MAX_ITERATIONS` env var on the agent-server side. 3
is the compromise the LDB paper reports as effective without inflating
end-to-end latency for simple bugs (which converge in 1 iteration).

### 9. Frontend: dedicated card + metric widget

- `VerifyStepCard` shows iteration counter, runner label, verdict
  badge, targets, exit code, and collapsible stdout/stderr tails. It
  parses `VerificationStep` out of the span's attributes with three
  fallback keys (`result`, `observation`, `verify_step`) so it is
  resilient to agent-server serialisation variations.
- `VerifyIterationsWidget` shows the retry high-water mark
  (`usedIter / maxIter`), the last verdict, and a colored chip strip
  showing the sequence of verdicts. It is derived client-side from the
  same `useTraceSpans(runId)` data — no new fetch.

## Consequences

### Wins

- **Zero server-side complexity added.** The BFF change is a single
  entry in a lookup dict.
- **The pattern generalises.** Any tool the agent can wrap in an
  `ActionEvent`/`ObservationEvent` pair with a new `tool_name` gets a
  new span kind for free, just by extending `_KIND_MAP`.
- **State is filesystem-local.** No shared DB, no cross-session
  interference, easy to reset.

### Costs

- **Verify subprocess time on every STOP.** Bounded by the runner's
  own speed — pytest for a single file is ~500ms on the Forge-OH repo.
- **Runner detection is heuristic.** Polyglot projects with
  unconventional layouts may need `runner_override`.
- **STOP-hook plumbing is agent-server-side.** The Forge-OH mirror
  ships the reusable primitives; the agent-server integrator must
  register the hook via `.openhands/hooks.toml`. That wiring is
  documented in BUILD_LOG.md's E.4 entry.

### Rejected alternatives

- **Full-suite verification on every STOP.** Too slow. Rejected.
- **Post-hoc BFF endpoint for verify stats.** Duplicates data already
  in the trace stream. Rejected.
- **Vendoring LDB.** Impedance mismatch too high. Rejected — see
  PORTING_LEDGER entry #2.
- **A separate `VerifyEvent` type in the event stream.** Would force
  changes across the SDK, agent-server, BFF, and frontend. The
  `tool_name="verify_step"` convention re-uses existing rails.
