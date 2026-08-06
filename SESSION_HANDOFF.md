# SESSION HANDOFF — 2026-08-06 10:15 EDT

## Current build-sequencing stage / plugin / port

**Stage 6.5 · Runtime model switching**

- §6.5.1 CLOSED (verdict PRESENT-as-REST, ADR-027 Ratified)
- §6.5.2 CLOSED (BFF endpoint `POST /runs/{run_id}/model` shipped, 32/32 tests green on Colossus at `f58f66c`)
- **§6.5.3 NEXT** — Frontend model-switch control in run-detail header

## What was completed this session

1. §6.5.1 output classified — three agent-server `switch_*` variants disambiguated; `switch_llm` picked as the only sound target.
2. ADR-027 Proposed → Ratified (rejects `switch_profile` + `switch_acp_model`, mandates preset-only wire contract).
3. Discovered ADR-012 §3 `MODEL_ROUTER_CATALOG` referenced but never landed → stopped and asked → landed as micro-slice `0242347` (18 tests, catalog + `is_model_compatible_with_role` oracle).
4. Shipped §6.5.2: `POST /runs/{run_id}/model` in `bff/routers/runs.py`, 14 pytest cases in `bff/tests/test_runs_model_switch.py`, all 32 tests green on Colossus at `f58f66c`.
5. BUILD_LOG appended for each landing.

## Commit stack on origin/main

- `f58f66c` **Stage 6.5.2: POST /runs/{run_id}/model (ADR-027) with 14 pytest cases**
- `0242347` ADR-012 §3 micro-slice: MODEL_ROUTER_CATALOG + compatibility oracle
- `936b5e7` ADR-027 Ratified: switch_llm-only BFF forwarding contract
- `0b0742b` Stage 6.5 §6.5.1 CLOSED: ADR-027 Proposed
- `85c08e3` SESSION_HANDOFF: Stage 6.4c CLOSED

## §6.5.3 scope for the next session

**⚠ SPEC SUPERSESSION — read before coding.**

`docs/reconciliation-plan-stage-6.md` §6.5.3 shows a browser body of:
```json
{"model": "...", "backendId": "..."}
```
That snippet is **stale**. ADR-027 (ratified 2026-08-06 09:52 EDT) supersedes it — the wire contract is:
```json
{"agentPresetId": "ap-1"}
```
No raw `model`, no `backendId`. Reason: credentials/model-source must never come from the browser; the BFF hydrates from the preset registry + secrets store. This is enforced at the Pydantic layer in `bff/routers/runs.py::SwitchModelRequest` and verified by `test_raw_model_field_is_ignored_at_pydantic_layer`.

**§6.5.3 Definition of Done**
- `src/features/run-detail/ModelSwitchControl.tsx` renders a preset picker (uses `useAgentPresets()` hook from Stage 2.2 — NOT `useInferenceBackends()` as the stale spec suggests).
- Selection triggers `POST /api/runs/{runId}/model` with `{ agentPresetId }`.
- On 200 → refresh run-detail header to reflect the new model badge.
- On 422 with `preset_model_incompatible_for_role` → user-visible error toast citing the preset and role.
- On 503 (`ModelUnavailableError`) → user-visible toast "model temporarily unavailable, try again shortly".
- On 404 → toast "run no longer exists".
- Vitest coverage for the component's happy path + 422 + 503 + 404.
- Playwright e2e:
  1. Start a run on `ap-1` (coder, vLLM).
  2. Switch to `ap-3` (coder, Ollama fallback) mid-run.
  3. Assert run-detail header updates.
  4. Assert next model-metadata event reflects the new backend.

**Stop condition**: DoD above met; header re-renders; vitest + Playwright green.

## Open questions / ambiguities awaiting user answer

None. Spec supersession is resolved (ADR-027 wins per `docs/reconciliation-plan-v1.md` newer-wins rule). §6.5.3 can proceed without further clarification once next session starts.

## Exact next action

Next session opens with:

```bash
cd ~/dev/forge-oh
git fetch origin && git reset --hard origin/main
cat SESSION_HANDOFF.md
cat src/features/settings/ModelSection.tsx      # existing picker pattern to mirror
cat src/features/agent-presets/hooks.ts          # confirm useAgentPresets shape
ls src/features/run-detail/                      # find the right header location
```

Then load skills: `forge-oh-slice-driver`, `forge-oh-colossus-ops`, `forge-oh-playwright-visual`, `forge-oh-debug-driver`.

Restate §6.5.3 scope from this file (spec supersession is critical — do NOT copy the stale `{model, backendId}` snippet from `docs/reconciliation-plan-stage-6.md`). Then implement `ModelSwitchControl.tsx`, wire it into the run-detail header, add vitest + Playwright, commit + push as `Perplexity Computer <computer@perplexity.ai>`, verify on Colossus with `bash scripts/forge-restart.sh` + Playwright spec (production build only, port 3100).

## Colossus quick reference

- Repo: `~/dev/forge-oh` on host "Collosus" (yes, that spelling)
- Venv: `~/dev/forge-oh/.oh-venv/`
- Dev-stack scripts: `bash scripts/forge-{up,down,restart,status,doctor}.sh`
- Playwright verify port: 3100 (production build; never `next dev`)
- BFF: `bff.main:app_with_sio` on 127.0.0.1:8081

## Signature

Commits signed as `Perplexity Computer <computer@perplexity.ai>`. Push via `bash` with `api_credentials=["github"]`.
