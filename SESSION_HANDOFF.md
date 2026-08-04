# SESSION_HANDOFF — 2026-08-04 02:47 EDT

## Current stage / component
F.19-post hotfix sequence, step 2 of the queued sequence just landed
locally (not yet merged): ADR-0001 amendment + supervisor user-scope
hygiene bundled slice. Forge-OH-Action-Plan-v4 has no formal stage
number for this work.

## What was completed this session

**Prior merged slices (main tip = `29ff23a`):**
1. G.1 self-eval harness (`d36e72a`).
2. Supervisor GPU-tenancy discipline (`117e263`, PR #1). 14/14 tests.
3. Code-default fix `qwen3-coder:30b` → `qwen3-coder:32k` in
   `bff/services/model_router.py` (`dcdcc6b`, PR #2).
4. vLLM-primary verification green on Colossus, logged in BUILD_LOG
   (`a698bd2`). 3/3 smoke tasks in 81s, all served by vLLM `:8501`.
5. DEBUG_LOG entry (`29ff23a`) identifying Ollama on `:11434` as a
   user-scope systemd unit (invisible to `systemctl is-active ollama`
   in system scope). 0 MiB VRAM at the time — did not affect the
   verified cycle.

**Current slice (`slice/adr-0001-amend-plus-supervisor-hygiene`,
NOT yet committed):**
6. `.openhands/decisions/001-use-ollama-first.md` — STATUS
   AMENDMENT block at top; status →
   `Amended · superseded by ADR-009 for F.19+ router`. Original text
   preserved.
7. `.openhands/context/decisions/001-use-ollama-first.md` —
   redirect-only amendment pointing to canonical copy + ADR-009.
8. `docs/adr/009-local-llm-selection.md` — Related line now
   explicitly says it supersedes ADR-001.
9. `ops/vllm_supervisor.sh` — `_stop_ollama` also runs
   `systemctl --user stop ollama` when the user-scope unit exists;
   `cmd_check` surfaces `ollama_listener: PRESENT on :11434` when
   `ss -lntp` matches.
10. `ops/test_supervisor.sh` — 4 new tests (7 new assertions);
    stub signatures extended. **21/21 tests PASS** (was 14/14).
11. BUILD_LOG appended (this slice entry).
12. SESSION_HANDOFF overwritten (this file).

## What remains before Definition of Done
1. Commit slice branch, push, PR, squash-merge to main, delete branch.
2. On Colossus: `git pull origin main`; supervisor + ADR changes now
   in place. No BFF restart required (this slice does not change
   any runtime code paths).
3. Optional / deferred: exercise the user-scope stop path on Colossus
   by deliberately starting a user-scope Ollama and running the
   supervisor's `check` cmd. Offline stubs already cover the
   behavior; on-host verification is nice-to-have, not blocking.

## Open questions / ambiguity
None open for this slice.

## Exact next action
1. Commit + push slice branch.
2. Open PR, squash-merge, delete branch.
3. On Colossus, `git pull origin main`.
4. Proceed to step 3 of the queued sequence:
   `slice/selfeval-frontend-polish` — first write a short scope doc
   listing the current `/selfeval` + `/selfeval/[date]` pages
   (from `src/app/selfeval/**`) + a fresh Playwright screenshot for
   the operator to review, get approval, THEN execute the polish
   + Playwright visual/workflow checks.

## Queued sequence status
1. **[DONE]** Step 1: vLLM-primary verification (`dcdcc6b` + `a698bd2`).
2. **[COMPLETE — awaiting merge]** Step 2: ADR-0001 amendment +
   supervisor user-scope hygiene (this slice).
3. **[NEXT]** Step 3: Self-Eval frontend polish scope doc → approval
   → polish → Playwright visual + workflow verification.

## State of Colossus at session close
- `forge-vllm-coder` container: expected `Up` on `:8501` (unchanged
  from last verified state).
- Ollama on `:11434`: user-scope systemd unit, idle listener, 0 MiB
  VRAM (documented in DEBUG_LOG `29ff23a`). Supervisor now knows
  how to stop it if it ever holds VRAM.
- BFF `:8081`: still running with `VLLM_SUPERVISOR_ENABLED=1`.

## Push credentials
`api_credentials=["github"]` — commit as
`Perplexity Computer <computer@perplexity.ai>`.
