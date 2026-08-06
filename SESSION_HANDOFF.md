# Forge-OH Session Handoff

## Current stage

**Stage 6.3 — CLOSED.** DoD met on Colossus 2026-08-06 05:48 EDT.

**Next stage: 6.4 — checkpoint-to-disk revert.** Not yet started.

## What was completed this session

**Stage 6.3 — Idempotency ledger:**
- Ledger service at `bff/services/idempotency_ledger.py` (aiosqlite, `completed_side_effects` table, INSERT OR IGNORE semantics, sort_keys canonical JSON hashing).
- Endpoints at `bff/routers/idempotency.py` — `POST /api/idempotency/check` + `POST /api/idempotency/mark`.
- Reusable mixin at `openhands_tools_ext/common/idempotent_executor.py` — talks to BFF over HTTP, fails open on network failure, bypasses ledger when `conversation=None`. Strips SDK `kind` discriminator from action dumps so arg-hash survives SDK upgrades.
- Synthetic `write_note` tool at `openhands_tools_ext/write/tools/write_note.py` — atomic tempfile+replace, deterministic filename via sha256(title)[:16].
- Test suites: 20 ledger unit + 10 endpoint (TestClient) + 6 mixin+tool with stubbed httpx = **36/36 passing** on Colossus.
- Crash-resume harness `scripts/test-crash-resume.sh` — real SIGKILL of a minimal uvicorn app; fresh process on the same on-disk DB sees the row + serves the cached payload; replay-mark returns recorded=false. **PASSED** end-to-end.
- `bff/main.py` lifespan wired for `init_db` + `close_db`; `scripts/forge-up.sh` preloads `write_note` in agent-server.

**Bug caught + fixed in the same session:** SDK v1.40.0 emits `kind` discriminator on `Action.model_dump()`. Pre-hotfix, this leaked into ledger arguments + arg-hash (would break upgrades). Fixed via `_EXCLUDED_ACTION_META_FIELDS` frozenset. Regression test locks it in. See DEBUG_LOG 2026-08-06 05:45 EDT.

## What remains before the next Definition of Done

Stage 6.3 is fully closed. Stage 6.4 has not been scoped yet.

## Open questions / ambiguities awaiting an answer

None blocking.

Non-blocking follow-ups from Stage 6.3:
- Memory E2E spec still carries pre-6.1 REPO_ROOT + `import.meta` bugs. Fix opportunistically.
- `write_note` stays registered — future stages (6.4 checkpoint revert, 6.7 code-exec MCP) can reuse it as a durable side-effect exemplar.

## Exact next action

Open **Stage 6.4 — checkpoint-to-disk revert** per `docs/reconciliation-plan-stage-6.md` §6.4:
1. Load `forge-oh-slice-driver` (already auto-loaded in Forge-OH sessions).
2. Restate §6.4 scope: stage boundary, plugin/port surface, DoD, stop condition.
3. Probe SDK for the actual checkpoint/revert primitives (do NOT assume the spec matches reality — Stage 6.3 taught us to always verify).
4. Flag any spec-vs-reality divergences.
5. Wait for user confirmation before writing code.
