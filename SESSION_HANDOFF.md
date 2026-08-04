# SESSION_HANDOFF

Last updated: 2026-08-03 21:41 EDT

## Current stage/plugin/port
Off-slice — audit + planning branch `audit/frontend-backend-parity` about to be pushed. Nightly self-eval harness slice `slice/g1-nightly-harness` is the next work to begin (branched off main).

## Completed this session
- Restarted BFF cleanly (dropped `--reload` — root-caused smoke-killer, logged in DEBUG_LOG). Ran F.19.4 Phase 2 smoke P1/P2/P3 all PASS on real vLLM.
- Cosmetic workspaceId fix (commit `abb06f7`) reverified green.
- **Audit branch created** (`audit/frontend-backend-parity`, off main @ `08fa3c4`):
  - `docs/frontend-backend-gap.md` — full parity map
  - `docs/decisions/2026-08-03-frontend-parity-plan.md` — F.20–F.31 slice plan
  - `docs/adr/010-frontend-parity-scope.md` — ADR-010 (Proposed)
  - `docs/kosmos-plugin-analysis.md` — code-only Kosmos assessment; NOT-NOW recommendation
  - Corrected Kosmos claims after user directive to trust code, not docs (Praxis/Phrouros/Zetesis all landed; Gnosis substantially built as kernel surrogate, not yet a plugin).
- Verified no nightly harness exists in Kosmos — pieces (Pier harness + DeepSWE runner + Makefile targets) are on-demand only; no timer or scheduled runner.
- Inventoried 7 Forge-OH project skills already authored (slice-driver, debug-driver, colossus-ops, llm-serving, porting, playwright-visual, bench-methodology).

## Remaining before current DoD
Nightly self-eval harness slice (G.1) — full DoD to be defined in ADR-011:
1. Cut `slice/g1-nightly-harness` off main.
2. Port Pier subprocess pattern from Kosmos `plugins/tektos/eval/harness.py` (Apache-2.0) into `openhands_tools_ext/nightly/`; log in PORTING_LEDGER.
3. Write manifest.toml (3 tasks), harness, LLM-propose-fix step.
4. systemd `.timer` + `.service` in `ops/systemd/`.
5. Author ADR-011.
6. One live smoke run.
7. `docs/skills-index.md` + README link.
8. BUILD_LOG + SESSION_HANDOFF + push.

## Open questions
None blocking. Task-manifest content (which 3 tasks) picked deterministically: reuse the DeepSWE-subset shape (Kosmos manifest is Apache-2.0), but seed with Forge-OH-flavored tasks — the manifest is meant to grow over time.

## Exact next action
Start the G.1 nightly harness slice. See `docs/decisions/2026-08-03-nightly-harness-plan.md` (to be written) and ADR-011 (to be authored).

## Runtime state at handoff
- BFF up on :8081 (no --reload)
- forge-vllm-coder up on :8501
- forge-vllm-planner DOWN (evicted; will auto-swap on next planner request)
- Ollama :11434 up
- Workspace UUIDs: forge-oh-repo=18c99443…, forge-oh-smoke=6dac22ae…

## Branches
- `main` @ `08fa3c4` — stable
- `audit/frontend-backend-parity` — pushed this session with audit deliverables
- `slice/g1-nightly-harness` — to be cut off main next
