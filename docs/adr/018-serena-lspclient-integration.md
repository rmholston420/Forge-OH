# ADR-018 — Serena LSPClient integration via MCP passthrough

**Status:** Accepted
**Lock-in phase:** Stage 4.4 (`LSPClient` port)
**Supersedes:** —
**Related:** `docs/reconciliation-plan-stage-4.md § 4.4`, `PORTING_LEDGER.md` (Serena entry 2026-08-06), ADR-006 (Repograph — Tier 2 of the retrieval cascade), ADR-004 (BFF middleware — the `/api/mcp` router this ADR reuses)

## Context

Stage 4.4 of the Forge-OH reconciliation plan requires adding a `LSPClient` port so the agent can do symbol-precise operations (`find_symbol`, `find_referencing_symbols`, `rename` / `replace_symbol_body`) that neither grep nor embeddings can provide. The plan proposes wrapping Serena (upstream: `oraios/serena`, GitHub).

While preparing Pass 3 the agent inspected the codebase and found the § 4.4 example code in the reconciliation plan is written against surface areas that do not exist in the current Forge-OH tree:

- Plan references `bff/config.py` with an `MCP_SERVERS` dict. Real file is `bff/settings.py` with a Pydantic `Settings` class; MCP servers live in the upstream agent-server's `agent_settings.mcp_config`, not in a BFF-side dict.
- Plan proposes a new `LSPAction` variant of an `EventCardType` discriminated union in `src/features/run-detail/types.ts`. Neither the union nor that types file exists — real event shape is a flat `ToolEvent { type: string, ... }` in `src/lib/schemas/event.ts`, and the card lives at `src/components/domain/EventCard.tsx` with icon lookup on `event.type`.
- Plan's Serena launch verb is `python3 -m serena start-mcp-server --workspace <ws> --port <N>`. Upstream Serena has no such invocation; the canonical launch verb is `uvx --from git+https://github.com/oraios/serena serena start-mcp-server --context ide-assistant --project <ws>` (stdio).

Rather than either silently adapt to what the plan literally says (which would ship broken code) or refuse to proceed, this ADR records the four locked design decisions and the plan corrections that flow from them, so Pass 3 can ship a working implementation whose divergences from § 4.4 are auditable in one document.

## Decision

### D1 — Registration path: idempotent bootstrap coroutine calling the existing `POST /api/mcp`

Add `bff/services/mcp_bootstrap.py::register_serena_if_missing()`. On BFF startup (lifespan hook, after `oh_startup()`), if `SERENA_ENABLED=true`:

1. `GET /api/mcp` (BFF's own MCP router, which passes through to agent-server).
2. If no entry has `id == "serena"`, `POST /api/mcp` with a `RegisterMcpRequest`-shaped body containing the Serena launch verb (see D2).
3. If any step fails, log a warning and continue. BFF startup must never crash on Serena bootstrap failure.

**Why not the plan's `MCP_SERVERS = {...}` in a config file:** that file does not exist and MCP state lives upstream, not in BFF. Reusing the production wire (`POST /api/mcp`) means we exercise the exact reshape + upstream POST that the UI depends on — if it's broken, we find out at boot.

**Rejected alternative:** call agent-server's `POST /api/settings/mcp/{name}` directly, bypassing BFF's router. Rejected because it silently degrades our test surface — a broken passthrough would still allow "startup success" while the UI shows an empty list.

### D2 — Serena launch verb: `uvx` with a pinned commit SHA

```json
{
  "name": "serena",
  "transport": "stdio",
  "command": "uvx",
  "args": [
    "--from", "git+https://github.com/oraios/serena@c7af2c09ef45faa4367c0e2a9f770fb73a62a612",
    "serena", "start-mcp-server",
    "--context", "ide-assistant",
    "--project", "<SERENA_WORKSPACE_DEFAULT>"
  ]
}
```

The SHA is `c7af2c09ef45faa4367c0e2a9f770fb73a62a612` — upstream `main` HEAD as of 2026-08-06 00:48 EDT. Recorded in `PORTING_LEDGER.md` for the same date and in `bff.settings.Settings.serena_pin_sha`.

**Rationale:**

- Upstream Serena is a `uv`/`uvx` tool. The plan's `pip install serena-agent` + `python3 -m serena start-mcp-server` invocations are not documented anywhere in the current README and do not work when tested against `main`.
- Pinning to a specific SHA (not a tag or `HEAD`) is required for reproducibility on Colossus, per the project's vendor-first porting discipline.
- `--context ide-assistant` is the upstream-recommended context for MCP clients embedded in coding-assistant workflows (Cline, Roo-Code, Cursor, and this codebase).

**Rejected alternative:** `uv tool install serena-agent` + `serena start-mcp-server`. Rejected because it requires a global PyPI package name that upstream does not currently document in the README's MCP section; `uvx --from git+...@<sha>` is the only path that ships a reproducible pin without depending on PyPI availability.

### D3 — Frontend: extend `EVENT_ICONS` + LSP badge, no schema change

Extend the icon map in `src/components/domain/EventCard.tsx` with LSP-family keys (`lsp_find_symbol`, `lsp_find_referencing_symbols`, `lsp_get_symbols_overview`, `lsp_replace_symbol_body`, `lsp_insert_after_symbol`, `lsp_insert_before_symbol`). Add an "LSP" badge in the card header for any `event.type.startsWith("lsp_")`. Backend `bff/services/event_normalize.py` promotes an ActionEvent's `type` from generic `"action"` to `lsp_<op>` when its `tool_name` matches a known Serena tool (matched on the last dotted segment so both `find_symbol` and `mcp.serena.find_symbol` resolve).

**Rejected alternative:** introduce a discriminated union `EventCardType = { kind: "ToolAction" } | { kind: "LSPAction", ... } | ...`. Rejected because the current frontend has no such union — event dispatching everywhere already discriminates on the string `event.type`. Adding a `kind` field would require rewriting every event consumer in the app for zero user-visible benefit.

### D4 — Language allowlist: no gate

Serena is registered unconditionally when `SERENA_ENABLED=true`. No language detection at registration time; no per-tool language check.

**Why:** Serena upstream already refuses unsupported languages internally and returns a clean error. Adding our own gate on top would be a duplicate defense with unclear semantics — the gate would either duplicate what Serena does, or would be a policy layer we haven't specified yet.

**Rejected alternatives:**

- **A1: Startup gate.** Only register Serena if the default workspace contains Python or TypeScript files. Rejected because "default workspace" is a boot-time snapshot; the user can switch workspaces after boot, and there's no per-workspace re-registration mechanism.
- **A2: Per-tool gate.** Refuse to dispatch Serena calls when the target file extension is not `.py`/`.ts`/`.tsx`. Rejected because this is a policy layer we have not specified (what about `.jsx`? `.rs` when someone adds a Rust language server?). Adding untested policy code raises risk without a concrete user requirement.

If Serena in practice returns confusing errors on unsupported languages, revisit as a follow-up ADR with A2 as the fallback.

## Consequences

### Positive

- Serena registration is idempotent and best-effort — no risk of BFF-startup regression.
- Reuses the existing `POST /api/mcp` production path — the same code path the UI depends on, exercised at boot.
- Frontend addition is additive and back-compatible — no `ToolEvent` schema change, no consumer rewrite.
- Pinned SHA guarantees reproducible Serena behavior across sessions.

### Negative

- BFF startup depends on itself (BFF calls its own `/api/mcp` endpoint before the app is fully bound to a port). Mitigated by: (a) the call is wrapped in try/except; (b) `httpx.ConnectError` is a known-swallowed failure mode; (c) test suite mocks the transport and covers connection-refused explicitly.
- First-run `uvx` on Colossus will resolve and cache the pinned Serena commit. If Serena upstream force-pushes and rewrites history, our pin becomes unresolvable and Serena registration silently fails until we bump the pin.
- No language gate means an agent could try `find_symbol` on a `.md` file. Serena will return an error; the agent will observe and retry. Acceptable UX for a Stage 4.4 pass; revisit if it becomes noisy.

### Neutral

- Serena tools appear in `GET /api/mcp` alongside any other MCP server the user has configured. This is the intended behavior — Serena is treated as one MCP server among many, not a special case.

## Verification

Definition of Done for this ADR's implementation:

1. `pytest bff/tests/test_mcp_bootstrap.py -q` green.
2. `pytest bff/tests/test_event_normalize.py -q` green (existing + 6 new LSP cases).
3. `pnpm test:unit src/tests/unit/EventCard-lsp.test.tsx` green.
4. With `SERENA_ENABLED=true` in `~/dev/forge-oh/.env` and BFF restarted:
   - `curl http://localhost:8081/api/mcp | jq '.[] | select(.id=="serena")'` returns a non-empty object.
   - `curl -X POST http://localhost:8081/api/mcp/serena/ping` returns `{"ok": true, ...}` with Serena tools listed.
5. This ADR file is checked into `docs/adr/` and referenced from `PORTING_LEDGER.md`, `BUILD_LOG.md`, and `docs/adr/README.md`.

Runtime end-to-end LSP tool invocation (an agent-driven rename) is deferred to the Stage 4 exit sweep and is not part of this ADR's DoD.
