# ADR-011: On-Demand Self-Eval Harness

- **Status:** Proposed
- **Date:** 2026-08-03
- **Slice:** G.1 (post-F, on-demand self-improvement loop)
- **Related:** ADR-007 (VerifyLoop) supplies the per-run verdict; ADR-008
  (Trajectory Memory) supplies the per-run structured record; ADR-009
  (Local LLM Selection) supplies the planner backend used by the
  proposer; ADR-010 (Frontend Parity, Proposed) supplies the sidebar
  layout `/selfeval` slots into.

## Context

Forge-OH now has the full closed-loop signal chain for a single run:
verify verdict → trajectory record → LLM planner. Nothing consumes
that signal chain across runs. Regressions are only caught when a
human happens to attempt a task the regression breaks.

The next unit of leverage is a **self-eval cycle**: a small,
hand-curated corpus of coding tasks the agent has to solve, run
end-to-end through the same BFF + agent-server + vLLM stack a user
would drive during the day. Failures surface as reviewable proposals
by the next morning, so the human's next work session begins with a
triage list instead of a blank slate.

**Launch model is on-demand, not scheduled.** rmholston's sleep
schedule is not fixed — some nights he goes to bed at 22:00, others
at 04:00. A fixed `.timer` at 02:30 would either fire while he's
still working (interfering with the coder vLLM warm state) or fire
after he's already up and paged the planner for something else. The
correct trigger is a "run before bed" button he hits himself.

The Kosmos Tektos plugin has related primitives
(`plugins/tektos/eval/harness.py` + `plugins/tektos/eval/corpora/deepswe/`)
but no on-demand launcher and no scheduled runner: it is a
Pier-subprocess batch driver invoked ad hoc for benchmarking, not a
regression watchdog. Forge-OH needs the watchdog shape, not the
benchmark shape. Vendoring the Kosmos code would drag in the Pier CLI
+ per-task Docker envelope, which Forge-OH does not need — a Forge-OH
task is just a prompt against an existing workspace.

## Decision

### 1. New in-repo module, not a plugin, not a Kosmos port

The harness lives at `openhands_tools_ext/selfeval/` alongside the
existing `verify/` and `trajectory/` modules. Four small files:

- `manifest.py` — typed TOML loader + selector (`head` / `random` / `tag:<name>`).
- `harness.py` — orchestrator: `POST /api/runs` per task, poll to terminal,
  read verdict from `TrajectoryStore`.
- `proposer.py` — planner-LLM-driven fix proposer that writes a single
  Markdown file per non-passing outcome.
- `cli.py` — CLI entry invoked by systemd (on-demand only) and by the
  BFF's on-demand launcher.

This composes with, but does not modify, the verify + trajectory + hook
subsystems. No new ports. No new adapters.

### 2. Manifest is source of truth; cycle size is per-run

Tasks live in `openhands_tools_ext/selfeval/manifest.toml` (TOML
`[[task]]` entries). The manifest is expected to grow. Every
invocation selects `--limit N` (env `FORGE_SELFEVAL_LIMIT`) tasks via
`--sample {head,random,tag:<name>}`. A "quick before-bed" run can
sample 3; a longer "before-weekend" run can sample 25 from the same
manifest.

Default limit is 3 (`SELFEVAL_DEFAULT_LIMIT`) — small enough that a
tired human doesn't hesitate to hit the button.

### 3. Serial execution, not parallel

Colossus has one agent-server conversation loop and one resident vLLM
model at a time (ADR-009 §3a). Running tasks concurrently would just
force supervisor swaps. The harness runs tasks strictly in sequence,
one BFF `POST /api/runs` at a time.

### 4. Failure signal reduction

Each task collapses into one of four verdicts:

- `passed` — BFF terminal `succeeded` AND latest verify verdict is `pass`
  (or verify was N/A).
- `failed` — verify verdict `fail`/`error`, OR trajectory `final_status`
  in `{failed, verified_failure, aborted}`, OR BFF terminal `failed`.
- `timeout` — per-task wall-clock cap tripped before terminal.
- `error` — BFF transport error, no run id returned, or unhandled state.

Reduction rules are ordered in `harness._score()`; timeout wins over
everything, verify verdict wins over trajectory status, trajectory
status wins over BFF top-level status. Deterministic and testable.

### 5. Fix proposer is Markdown-only, never auto-applied

For every non-passing outcome, `proposer.propose_fixes()` sends the
compact context (task description, last 3 verify iterations, diff
summaries, symbols touched) to the planner LLM
(default `http://localhost:8511/v1/chat/completions`, model
`qwen3-thinking-2507-awq`, matching ADR-009) with a strict system
prompt that forces a fixed Markdown structure. The response is written
verbatim to `docs/proposals/YYYY-MM-DD-<task_id>-<run_id_short>.md`,
with a metadata comment header and the input context embedded as a
collapsible JSON block.

Filename collisions append `-v2`, `-v3`, etc. — a same-day re-run never
overwrites history.

**Auto-apply of proposals is out of scope forever.** The whole point is
morning triage; a proposer that patches its own repo without review is a
foot-cannon.

### 6. Two launch surfaces, one code path: BFF Run-now (primary) + systemctl (fallback)

Both surfaces call the same `python -m openhands_tools_ext.selfeval.cli`.
Both write to the same `docs/selfeval/` + `docs/proposals/` directories.
The frontend `/selfeval` page does not distinguish between cycles by
launch source.

**BFF Run-now (primary)** — `POST /api/selfeval/run` shells out to
`systemctl --user start forge-oh-selfeval.service` and returns
immediately with the cycle's start time. A BFF-scoped `asyncio.Lock`
(with in-memory `{running, started_at, systemd_result}` state) enforces
one-cycle-at-a-time; concurrent `POST /run` returns 409 with the
current cycle's status. `GET /api/selfeval/status` exposes that state
to the frontend so the Run-now button can disable itself while a cycle
is in flight. Going through `systemctl` (rather than
`asyncio.create_subprocess_exec`) gives us journald history, clean
`systemctl --user status` visibility, and standard cgroup resource
limits for free — worth the runtime dependency on user-scoped systemd
(which Colossus already runs; `bff/services/hook_config.py` assumes it).

**systemctl direct (fallback)** — `systemctl --user start
forge-oh-selfeval.service` from any terminal. Same one-shot unit.
Useful for pre-bed runs when the GUI is closed, or for debugging.

**No `.timer`. No cron. No fixed cadence.** If rmholston wants a fixed
cadence in the future, a `.timer` can be added in a follow-up ADR
without touching this ADR's decision.

The unit itself is user-scoped (`~/.config/systemd/user/`, i.e.
`systemctl --user`). No system-wide install. No privilege escalation.
No network beyond localhost.

### 7. GUI: dedicated `/selfeval` page + top-level sidebar entry

Slot A per user direction (2026-08-03): a new top-level sidebar item
labelled **Self-Eval** (alarm-clock icon) after **Trajectories**. Pages:

- `/selfeval` — latest cycle KPIs, cycle history table, **Run now**
  button. Run-now disables while `GET /status` reports `running`.
- `/selfeval/[date]` — full per-task outcome table for that cycle;
  each row deep-links to `/runs/{run_id}` (existing Trace tab), plus a
  Proposals section rendering each `docs/proposals/*.md` for the day
  using the existing Markdown component.

Manifest editing and proposal editing are NOT exposed in the UI — VS
Code owns editing. The GUI is read + trigger only.

### 8. Storage layout

- Cycle summaries: `docs/selfeval/YYYY-MM-DD-selfeval.json` (schema =
  `SelfEvalSummary.to_dict()`). Multiple cycles in one calendar day
  collide on filename; the second cycle's file appends `-HHMM`.
- Proposals: `docs/proposals/YYYY-MM-DD-<task_id>-<run_id_short>.md`.
- Neither directory is in `.gitignore` — passing streaks are durable
  historical evidence, failure proposals are auditable artifacts.

## Alternatives Considered

- **Fixed nightly `.timer` at 02:30**: rejected. rmholston's bedtime
  varies; a fixed schedule would misfire relative to the "run this
  before I go to bed" workflow that motivates the whole feature. A
  `.timer` may be added in a future ADR if a cadence emerges.
- **Vendor Kosmos `plugins/tektos/eval/`**: rejected. The Pier/Docker
  envelope is a heavier abstraction than Forge-OH needs. We DID borrow
  the shape (one manifest, one verdict per task, aggregated summary) as
  pattern, not code — no `PORTING_LEDGER` entry required.
- **`asyncio.create_subprocess_exec` from BFF, no systemd**: rejected.
  Loses journald history + `systemctl --user status` visibility + cgroup
  resource limits. Colossus already runs user-scoped systemd; keeping the
  extra one-hop is worth the free instrumentation.
- **Cron via user crontab (on-demand only, no schedule)**: rejected.
  Cron is a scheduler; using it as a launcher is misuse and inherits
  the same schedule-mismatch problem.
- **BFF-in-process scheduler (APScheduler etc.)**: rejected. No fixed
  cadence is wanted; a scheduler with no schedule is dead weight.
- **Manifest in the database instead of TOML**: rejected. The manifest
  is code-review material; keeping it as a tracked TOML file lets slice
  reviewers see corpus growth in PRs.
- **Auto-apply proposals with a confirmation prompt**: rejected outright
  (see §5). Never.

## Consequences

- New files: `openhands_tools_ext/selfeval/{__init__.py,manifest.py,harness.py,proposer.py,cli.py,manifest.toml}`, `openhands_tools_ext/tests/selfeval/{test_manifest.py,test_harness.py,test_proposer.py}`, `ops/systemd/{forge-oh-selfeval.service,README.md}`, `bff/routers/selfeval.py` (+ tests), `src/app/(dashboard)/selfeval/{page.tsx,[date]/page.tsx}` (+ Playwright smoke), `docs/adr/011-selfeval-harness.md`.
- Modified files: `bff/main.py` (+1 router mount), `src/components/Sidebar.tsx` (+1 nav item).
- No changes to verify or trajectory subsystems; no changes to model_router.
- No new Python dependencies. `httpx` + `tomllib` + `pydantic` already present.
- Two new disk directories: `docs/selfeval/`, `docs/proposals/`. Neither
  is tracked-empty; they materialize on first run.
- BFF gains a `systemctl --user` shell-out capability guarded by a
  single-cycle asyncio.Lock. The lock is per-process, not per-machine:
  two BFFs on the same box would race on the proposal filenames but the
  `-v2` suffix logic handles that gracefully; a `--flock` refinement is
  left as a future ADR if a second BFF ever materializes.

## Definition of Done (slice G.1)

1. `openhands_tools_ext/selfeval/` module + manifest committed, unit
   tests passing (`test_manifest.py` + sync half of `test_harness.py` +
   `test_proposer.py` all green in-sandbox; async tests green with
   `pytest-asyncio` in CI).
2. `ops/systemd/forge-oh-selfeval.service` + README present;
   `systemd-analyze verify` clean on a Colossus install.
3. `bff/routers/selfeval.py` with `/cycles`, `/cycles/{date}`,
   `/proposals`, `/proposals/{filename}`, `POST /run`, `GET /status`.
   Path-traversal guards on every filename param; tests covering happy
   + traversal-attempt paths.
4. `/selfeval` + `/selfeval/[date]` pages rendered and reachable via a
   new top-level sidebar entry. Run-now button posts to
   `/api/selfeval/run`, disables via `GET /status`. Playwright smoke
   covers "sidebar → page → Run-now enabled when idle".
5. One live end-to-end cycle executed on Colossus (Run-now path OR
   `systemctl --user start`) that produces a summary JSON + at least
   one proposal file. Contents inspected by human.
6. ADR-011 status flipped from Proposed → Accepted after §1–§5 above.

## References

- `openhands_tools_ext/selfeval/__init__.py` — subsystem docstring
- `openhands_tools_ext/selfeval/manifest.toml` — starter corpus
- `bff/routers/runs.py::create_run` — the surface the harness invokes
- `openhands_tools_ext/trajectory/schema.py::TrajectoryRecord` — verdict source
- `openhands_tools_ext/verify/schema.py::VerificationStep` — per-iteration verdict
- Kosmos `plugins/tektos/eval/harness.py` — pattern reference (not vendored)
