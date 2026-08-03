# SESSION_HANDOFF

## Current stage
Step 7 — remaining OpenHands surfaces. Slice A ✅, Slice B ✅ (visual QA
proved KPI cards populated). Slice B fix pushed as `1d1efe9` to correct
"unknown" model/workspace labels.

## Slice B fix (pending visual QA)
- Model resolution: fall back to `agent.llm.model` when
  `metrics.model_name` is empty (queued-but-never-run conversations).
- Workspace resolution: use `working_dir` first (real LocalWorkspace
  schema), keep legacy fallbacks for compat.
- 11 unit tests pass locally (including new TestModelFallback).

## Next action (RUN ON COLOSSUS)
```bash
cd ~/dev/forge-oh
git pull --ff-only
./scripts/forge-test.sh
./scripts/forge-screenshots.sh
```

## Expected visual result
- `20-metrics-dashboard.png`: "By model" now shows
  `openai/qwen3.6:35b-a3b` (or whatever the agent-server is configured
  with), "By workspace" shows the real `working_dir` (e.g. `/workspace`
  or the container mount path). No more `unknown` labels.

## Slice C candidates (after fix verifies)
1. **VSCode / Desktop quick links** — upstream `/api/vscode/url` +
   `/api/desktop/url` are real. Add BFF passthrough + small run detail
   header buttons. Isolated change.
2. **Real git diff wiring** — upstream `/api/git/diff/{path}` +
   `/api/git/changes/{path}`. File-diff currently reconstructs from
   events. Wiring real git output improves precision.
3. **Live bash streaming** — upstream `/api/bash/*` bash_events. Bigger
   scope (SSE relay integration into terminal emulator).

## Open questions / ambiguities
None.
