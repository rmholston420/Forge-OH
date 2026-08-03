# Session Handoff — 2026-08-03 12:15 EDT

## Current State
- **F.16 (GPU monitor)**: COMPLETE + Colossus-verified. Poller, `/api/gpu` + `/api/gpu/history`, PRE-tool hook, always-visible top-right GPU strip. Cutoffs: warn 52 C, cap 83 C, crit 88 C, power cap 435 W. Playwright screenshot spec (`gpu-strip.spec.ts`) auto-commits + pushes PNGs to origin/main. Live sample on idle 5090: T 32 C · U 0% · V 23% · 19 W (all green).
- **G.1 (self-testing)**: COMPLETE + Colossus-verified. Agent reads a spec, writes a new pytest case to `TestSymptomProducer` with the correct event shape, and the new case passes in isolation (31 s run).
- **F.17**: cut per user decision (G.1 supersedes).

## What Remains
- Nothing on the current stop-condition. Ready to pick next slice.

## Open Options (user requested evaluation)
1. **F.18 vLLM backend** — already running on Colossus; router swap likely a URL change + payload adjustment. Small slice, real perf win.
2. **F.16 polish** — GPU history sparkline / mini-trend chart consuming `/api/gpu/history`.
3. **Sidecar producer coverage** — more `Producer.observe` cases; leverage G.1's proven agent-writes-tests capability.
4. **Backfill task_description on pre-F.12 orphan runs.**
5. **Retention policy ADR for `trajectories.db`.**
6. **Fix 14 pre-existing `httpx.ConnectError` failures** in `test_mcp_router.py` / `test_observability_router.py` / `test_plugins_router.py` — need agent-server on :8090 or a proper offline deselect.
7. **Caddy HMR fix** — Turbopack HMR websocket handshake fails via Caddy in fresh Chromium (works in your regular browser because of cached state). Not blocking, but foundational hygiene.

## Ambient
- Next prod server may still be running on 127.0.0.1:3100 from screenshot spec (started manually — Playwright didn't manage it). Kill with `fuser -k 3100/tcp` when done.
- Frontend dev server on 3000 was killed during debugging; restart with normal flow.
- BFF on 8081, workspace ID `18c99443b23c452899010095abd5f29b`, preset `ap-1`.

## Next Action
User is evaluating options. Await direction.
