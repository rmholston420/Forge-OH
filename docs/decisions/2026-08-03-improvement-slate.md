# Improvement Slate — 2026-08-03

Answers to the six questions raised after F.14/F.15 landed. This is
a **decision doc**, not a locked ADR — pick items to promote to
build slices.

## Q6 (settled first) — Are D/E/F plugins? Do they load by default?

**No.** Forge-OH does not use the OpenHands `PluginDescriptor`
mechanism. Slices D/E/F ship as in-repo modules under
`openhands_tools_ext/{repograph,verify,trajectory}` and are wired
into every conversation by `bff/services/hook_config.py`, which
attaches two subprocess `HookType.COMMAND` hooks (`forge-oh-verify`,
`forge-oh-trajectory`) to the STOP matcher of every new run. Nothing
to enable — they run for every conversation the BFF creates.

The `/api/plugins/*` router is a passthrough to the agent-server's
own plugin subsystem (LiteLLM providers, upstream extensions). It's
unrelated to slices D/E/F.

## Kosmos / Tektos survey

Cloned `rmholston420/kosmos` and inspected the Tektos plugin. Four
components are directly reusable in Forge-OH; none require porting
the Kosmos kernel or ports layer.

| Component | Kosmos path | Reusable pattern for Forge-OH |
|---|---|---|
| **Pier eval harness** | `plugins/tektos/eval/harness.py` | Subprocess-invokes a public CLI (Pier), parses trajectory, records one MemoryPort event per trial (`tektos.eval.trial_completed`). Mirror shape: Forge-OH already has `TrajectoryRecord` + `TrajectoryStore`; add a "run a fixed task through Forge-OH and record verdict" wrapper the same way. |
| **DeepSWE corpus loader** | `plugins/tektos/eval/corpora/deepswe/` | Ready-made frozen corpus (manifest.toml + policy + loader). If we bring the corpus in via a pinned git submodule or a downloaded artifact, we get instant baseline benchmarks. |
| **OpenSpec plan producer** | `plugins/tektos/openspec/` | Parses `openspec/changes/<id>/{proposal.md, tasks.md, design.md, specs/…}` into a typed `Plan`. Directly usable as the "structured spec input" for Forge-OH's coding agent — closes the gap the F.15 producers exposed (no `TaskTrackerAction` in `ap-1`). |
| **RepoMap** | `plugins/tektos/repomap/` | Tree-sitter tags → PageRank over identifier reference graph → token-budgeted rendered map. Complements Forge-OH's Neo4j `RepoGraph` (slice D.5): RepoMap gives a *token-bounded* prompt-time context slice; RepoGraph gives an *unbounded* queryable index. They coexist. |

Not reusable: the ports/kernel layer, plugin descriptor registration,
UI panel/route contract — Forge-OH is not port-oriented.

## Top 3 fastest wins (ranked by effort ÷ payoff)

### 1. Verify-loop grep of DEBUG_LOG.md before diagnosing new errors

**Effort:** ~1 hour. **Payoff:** every recurring bug fix becomes O(1)
lookup instead of O(N) re-diagnosis, exactly the workflow the project
instructions already prescribe but that isn't enforced in the loop.

Currently `openhands_tools_ext.verify.loop` runs failing tests and
asks the LLM to diagnose. Add a pre-diagnosis step that:

1. Extracts the failing symptom string (test name, exception type,
   error message).
2. Greps `DEBUG_LOG.md` for the same symptom.
3. If a matching entry exists, prepends `## KNOWN ISSUE — see DEBUG_LOG.md {timestamp}\n<entry body>` to the LLM prompt.

Files: new `openhands_tools_ext/verify/debug_log_index.py`, hook
into `verify/loop.py::iterate`.

### 2. Self-expanding test coverage via a trajectory-driven coverage bot

**Effort:** ~1 slice (G.1 candidate). **Payoff:** durable — every
merged change grows the safety net.

The seed loop:

1. Cron (or manual) invokes a Forge-OH run with a canned prompt:
   *"Read `coverage.xml`. Pick the file with the lowest branch
   coverage that has no test file. Write a pytest module. Run it.
   Iterate until it passes."*
2. Verify hook enforces green tests as the stop condition.
3. Trajectory writer records success/failure to `trajectories.db`.
4. A drain-time filter promotes verified successes into a PR.

Preconditions already met: F.14 gives us `final_status`, F.15 gives
diffs, sidecar carries the plan. Missing piece: the canned prompt +
a coverage.xml producer step. Both are ~50 lines.

Direct port from Tektos: reuse the Pier harness pattern from
`plugins/tektos/eval/harness.py` — swap the Pier CLI for
`python -m openhands_tools_ext.trajectory.hook`.

### 3. Structured verdict on every run, not just verify-driven ones

**Effort:** ~half slice. **Payoff:** learning signal on every run.

Today `symptom` is only populated when a tool errored or verify
fails. Extend the F.15 symptom producer to also probe the LLM's
`FinishAction.message` — the finish action often names the failure
in prose ("I couldn't get X to work because Y"). Parse that with a
small extractor and store it as `symptom` when nothing else fired.

Files touched: `bff/services/sidecar_producers.py` only. New
producer: `_produce_symptom_from_finish_action`. Feed into the same
merge path as the existing observation/hook producers.

## Q — Should the coding agent enforce "Python best practices"? Plugin, skill, or something else?

**Recommendation: a verify-loop rule set, not a plugin or an
agent-level system-prompt skill.**

Rationale:

- Best-practices enforcement is a **verifiable property** of the
  output code (ruff, mypy, pytest, bandit, radon). Verifiable
  properties belong in the verify loop, which already runs after
  every code-writing turn. Adding a plugin or SDK "skill" moves the
  check to *prompt time*, where the agent can rationalize around
  it.
- Forge-OH's verify loop (slice E) already supports pluggable
  runners. Add a `openhands_tools_ext/verify/rules/` package:
  each rule is a subprocess spec (`ruff check --output-format json`,
  `mypy --strict`, `bandit -r`, `radon cc -s -a -n B`) that returns
  a structured verdict.
- Config lives in `.forge-oh/rules.toml` at the workspace root, one
  toggle per rule. Ships with a Forge-OH default preset (`ruff` +
  `mypy` on by default; `bandit` + `radon` opt-in).
- When any rule fails, the verify loop emits a
  `HookExecutionEvent` with `verdict=failed` and the tool name in
  `reason` — which the F.15 symptom producer already picks up
  end-to-end (verified 10:56 EDT).

A "system-prompt skill" (i.e. injecting "please follow PEP-8" into
every prompt) is worse because the agent may or may not obey. The
verify loop is a hard gate.

Kosmos analogue: `plugins/tektos/eval/policy.py` shows the shape —
constants + a small confidence function, wired through the memory
port. Copy the shape, drop the port coupling.

## Q — GPU temperature monitoring

**Recommendation: a small BFF slice, no new port surface.**

Design:

1. **Poller** — `bff/services/gpu_monitor.py`, a background asyncio
   task started in `bff/main.py::lifespan`. Polls
   `nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits`
   every 2 seconds (configurable via `FORGE_GPU_POLL_SEC`).
2. **Ring buffer** — last 15 minutes of samples in memory, keyed by
   GPU index. Cheap; ~450 samples × 6 floats.
3. **Route** — `GET /api/gpu` returns current sample; `GET /api/gpu/history?window=<sec>` returns the ring slice.
4. **Thermal cutoff hook** — new subprocess hook
   `openhands_tools_ext/gpu/hook.py` registered against a PRE-tool
   matcher (or the SDK's tool-call event). If
   `temperature.gpu >= FORGE_GPU_TEMP_CUTOFF_C` (default 83°C for
   Blackwell 5090, well below the 90°C thermal throttle floor), the
   hook returns non-zero and the SDK skips the tool call this turn
   with `reason="gpu thermal cutoff"`. The trajectory sidecar
   already captures that via F.15 → `symptom` field.
5. **Frontend** — one new panel on the run detail page reading
   `/api/gpu/history` and rendering a sparkline.

Slice budget: half a day. Zero new ports. No agent-server changes
required — the hook attaches at BFF-side `hook_config.py`.

## Q — Full playwright coverage of the frontend

Deferred to a dedicated slice. This session's Playwright deliverable
is a **smoke** authoring pass under
`src/tests/e2e/f15-fixups.spec.ts`:

- Fires a happy-path run via `POST /api/runs`, polls for
  `data.status === "succeeded"`.
- Fires a failing-terminal-command run.
- Reads `trajectories.db` via a Python one-liner (matches the
  pattern in `trajectory-memory-panel.spec.ts`).
- Asserts:
  - happy run has `final_status="success"`, non-empty `diffs_json`,
    empty `symptom`.
  - failing run has non-empty `symptom` containing
    `"TerminalObservation exit=1"`.

The full existing suite (18 specs under `src/tests/e2e/`) already
covers runs, workspaces, plugins, observability, RepoGraph,
trajectory memory, secrets, and settings. No further authoring
needed for smoke; a full coverage sweep is a G-slice conversation.

## Summary — build order I'd recommend

If you promote any of these to build slices:

1. **F.16 — Best-practices verify rules** (highest leverage, smallest
   surface area).
2. **F.17 — GPU thermal monitor** (protects hardware, unblocks
   overnight benchmarking).
3. **G.1 — Coverage bot** (self-improving; depends on stable F.14/F.15
   verdicts, which we now have).

Kosmos ports (OpenSpec parser, DeepSWE loader) get bundled into G.1
when we need typed corpora.
