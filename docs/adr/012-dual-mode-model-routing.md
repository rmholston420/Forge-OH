# ADR-012: Dual-Mode Model Routing — Role-First with Preset Model Override

- **Status:** Accepted
- **Date:** 2026-08-04
- **Slice:** `slice/dual-mode-routing-adr` (Stage 1 reconciliation-plan-v1, sub-slices 1.5.3–1.5.5)
- **Supersedes:** [ADR-009 §1, §2, §3, §3a](./009-local-llm-selection.md) at the *routing-layer contract*. ADR-009's evidence, topology decision (§3a dual-port + swap-on-demand supervisor), token budgets (§3b), and vLLM Blackwell operational notes (§5) remain load-bearing and are cited from here.
- **Related:** [`bff/services/model_router.py::route_by_role`](../../bff/services/model_router.py), [`bff/routers/runs.py::create_run`](../../bff/routers/runs.py), [`bff/routers/agent_presets.py`](../../bff/routers/agent_presets.py), Reconciliation-plan-v1 §1.5.3–1.5.5, [`SESSION_HANDOFF.md`](../../SESSION_HANDOFF.md) 2026-08-04 21:57 EDT resolution.

## Context

ADR-009 §1–§3a locked routing to **role-based dispatch**: `route_by_role(role, context_length)` returns a `RoleRoute` for `role ∈ {coder, planner}`, and `create_run` picks the role from either an explicit `body.role` or a `_TASK_COMPLEXITY_TO_ROLE` map. Under this contract, `AgentPreset.model` (a `Literal["gpt-4o", "claude-opus-4", "gemini-2.5-pro", "local-llama"]`) has never been consulted for routing — it is echoed back as `agentPresetName` in the response and nothing more.

Forge-OH-reconciliation-plan-v1 §1.5.3–1.5.5 asks for three coupled changes:

1. **1.5.3** — replace the cloud-model `Literal` in `agent_presets.py` with model IDs validated against the `model_router` catalog.
2. **1.5.4** — make `create_run` route by `preset.model` instead of by role.
3. **1.5.5** — persist `_PRESETS` from an in-memory dict to SQLite.

Item 1.5.4 as literally worded contradicts ADR-009 §3a (single-role residency, swap-on-demand). The operator's resolution (SESSION_HANDOFF 2026-08-04 21:57 EDT, open question #1 → option b) is: **supersede ADR-009's routing contract with a dual-mode scheme where role-based routing remains canonical and takes precedence; preset-driven model selection layers on top only when compatible with the resident role's model.**

Two options were considered before landing on the decision below:

- **A. Preset-first with role fallback.** `preset.model` picks the model directly; `role` is used only when preset is null. Rejected: reintroduces the single-role-residency violation ADR-009 §3a was written to prevent — an operator could pin a preset to the planner model while a coder-role task is dispatched, forcing per-request vLLM swaps.
- **B. Role-first with preset override, compatibility-gated.** Role determines which vLLM instance is resident and its token budget; preset may substitute an alternative model from that role's approved compatible set. If preset's model is not compatible with the resolved role, the router logs a downgrade event and falls back to the role's canonical model. Chosen — meets operator's stated intent ("both routing by role and preset-driven model routing with routing by role taking precedence") without inviting resident-model swaps.

## Decision

### 1. Two-pass routing in `create_run`

The routing pass in `bff/routers/runs.py::create_run` runs in two stages:

1. **Role resolution (unchanged from ADR-009 §3a).** Compute `role` via the existing precedence: `body.role` → `_TASK_COMPLEXITY_TO_ROLE[taskComplexity]` → `"coder"`. Call `route_by_role(role, context_length)` to resolve the base `RoleRoute` (backend, base_url, canonical model, max_tokens).
2. **Preset override.** Look up the preset by `body.agentPresetId`. If the preset carries a non-null `model` field AND that model is present in `MODEL_ROUTER_CATALOG[role].compatible_models`, replace `route.model` with `preset.model` while preserving `route.backend`, `route.base_url`, and `route.max_tokens`. Otherwise, leave `route` unchanged and emit a `preset_model_incompatible` downgrade event to the sidecar producer.

Role always wins on **which vLLM instance is resident** (base_url) and **which token budget applies**. Preset only substitutes the served-model-name string sent to LiteLLM, and only when the substitution is legal for the resident role.

### 2. `AgentPreset.role` field

`bff/routers/agent_presets.py::AgentPreset` gains a required field:

```python
role: Literal["coder", "planner"] = "coder"
```

The preset's `role` is **advisory**: it is exposed in the API response so the frontend can show "This preset targets the coder role", but `create_run` does NOT consult `preset.role` for routing. Role selection remains driven by `body.role` / `taskComplexity` per ADR-009 topology. `preset.role` exists to constrain which `model` values are legal on that preset (see §3) — a coder-role preset cannot carry a planner-only model.

### 3. `AgentPreset.model` catalog

The `ModelId = Literal[...]` in `agent_presets.py` is replaced with runtime validation against a new `MODEL_ROUTER_CATALOG` in `bff/services/model_router.py`:

```python
# Seed as of ADR-013 ratification (planner only; coder pending Path F).
MODEL_ROUTER_CATALOG: dict[str, RoleCatalog] = {
    "coder":   RoleCatalog(
        canonical="qwen3.6-35b-a3b-nvfp4",       # ADR-009 default retained; ADR-013 defers coder to Path F
        compatible={"qwen3.6-35b-a3b-nvfp4", "qwen3-coder-30b-awq", "devstral-24b-awq"},
    ),
    "planner": RoleCatalog(
        canonical="deepseek-r1-distill-32b-awq", # ADR-013 Path E winner (2026-08-05)
        compatible={"deepseek-r1-distill-32b-awq", "qwen3-thinking-2507-awq"},
    ),
}
```

- `canonical` is the ADR-009-selected model for that role. It is what `route_by_role` returns absent any preset override.
- `compatible` is the set of alternative models the operator has certified as legal substitutes on the same resident vLLM instance (or its role-specific Ollama fallback). Any model outside the set triggers the §1 downgrade path.
- The coder set includes the `qwen3-coder:32k` Ollama fallback (ADR-009 §2 / DEBUG_LOG 2026-08-04) so a preset targeting the fallback path is legal.
- Preset create/update requests validate `model ∈ MODEL_ROUTER_CATALOG[role].compatible` at the API boundary (422 on violation), so an incompatible preset can never be persisted in the first place.

### 4. SQLite persistence for `_PRESETS`

The in-memory `_PRESETS: dict[str, AgentPreset]` is replaced with a SQLite-backed store at `~/.forge-oh/agent_presets.db`. Schema:

```sql
CREATE TABLE agent_presets (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT,
    system_prompt  TEXT NOT NULL DEFAULT '',
    role           TEXT NOT NULL CHECK (role IN ('coder','planner')),
    model          TEXT NOT NULL,
    max_steps      INTEGER NOT NULL DEFAULT 100,
    max_cost       REAL NOT NULL DEFAULT 5.0,
    temperature    REAL NOT NULL DEFAULT 0.2,
    top_p          REAL NOT NULL DEFAULT 0.95,
    tool_allowlist TEXT NOT NULL DEFAULT '[]',   -- JSON array
    loop_guard     TEXT NOT NULL DEFAULT '{}',   -- JSON object
    is_default     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE UNIQUE INDEX ix_agent_presets_default
    ON agent_presets(is_default) WHERE is_default = 1;
```

- The unique-index-on-default enforces "at most one default preset" at the storage layer, matching current in-memory `set_default` semantics.
- On first startup, if the table is empty, the two seed presets (`ap-1` General Dev, `ap-2` Research Agent) are inserted with their existing IDs so the frontend's default-preset lookup (`bff/routers/runs.py::_resolve_default_preset_id`, `forge-oh-colossus-ops` triage playbook) keeps working without a migration.
- Migration surface is zero for existing Colossus operators — the SQLite DB is created on demand and seeded on first read.

## Rationale

- **Role-first preserves ADR-009 §3a topology.** Only one vLLM instance is resident at a time, and its resident instance is decided by role, not by preset. The dual-port swap-on-demand supervisor's assumption holds unchanged.
- **Preset-driven substitution is confined to same-role alternatives**, so an operator experimenting with a new coder GGUF can wire it in via a preset without triggering an instance swap or a budget change.
- **Compatibility gating is authoritative at API boundary.** Rejecting incompatible presets at PATCH/POST time (422) prevents runtime downgrade events from ever firing under normal operator flow; the runtime downgrade path exists only as a safety net for stale presets after a catalog change.
- **SQLite persistence is unblocked** by decoupling routing from preset shape — the DB stores whatever the model-router catalog validates.
- **No frontend change to run creation flow.** The frontend already sends `agentPresetId`; it now has real routing consequences instead of being an echo field.

## Consequences

**Files changed under this ADR:**

- `bff/services/model_router.py` — new `RoleCatalog` dataclass and `MODEL_ROUTER_CATALOG` constant; new `resolve_preset_route(role, preset_model, context_length)` helper that wraps `route_by_role` with the override logic; new `ModelIncompatibleWithRoleError` exception.
- `bff/routers/agent_presets.py` — `ModelId` `Literal` removed; `role` field added to `AgentPreset`, `CreateRequest`, `UpdateRequest` (default `"coder"`); model+role validated against `MODEL_ROUTER_CATALOG` on POST/PATCH; `_PRESETS` dict replaced with SQLite-backed store.
- `bff/routers/runs.py::create_run` — after `route_by_role`, look up preset; if `preset.model` is compatible with the resolved role, override `route.model`; else emit downgrade event and proceed with canonical.
- New SQLite migration entry-point at BFF startup (idempotent `CREATE TABLE IF NOT EXISTS`, seed on empty).
- `src/features/agent-presets/*` — preset create/edit UI gains a `role` selector; model dropdown filters by selected role using a new `GET /api/agent-presets/catalog` endpoint that exposes `MODEL_ROUTER_CATALOG`.
- `docs/adr/009-local-llm-selection.md` — status line amended: `Accepted · superseded by ADR-012 at the routing-layer contract`.
- `docs/adr/README.md` — ADR index entry added (creating the index file as a side effect).

**Tests to add:**

- Unit: `bff/tests/test_agent_presets_role_validation.py` — POST/PATCH with model outside `role.compatible` returns 422; POST with model in set is persisted; role migration seed keeps `ap-1` `isDefault=true`.
- Unit: `bff/tests/test_dual_mode_routing.py` — `create_run` with preset carrying compatible model uses preset model; incompatible preset falls back to canonical AND emits downgrade sidecar event; missing preset falls back to canonical without event.
- Integration: `bff/tests/test_agent_presets_sqlite.py` — DB is created on first read, seeded when empty, respects unique-default index (409 on second `set_default` collision guard).

**Follow-ups:**

1. `pplx.frontend`: catalog endpoint + role-filtered model dropdown in preset editor.
2. Consider extending `MODEL_ROUTER_CATALOG` to carry per-model max_tokens overrides if the coder-role's canonical budget (2048, ADR-009 §3b) proves too tight for a specific compatible substitute. Not required for the initial slice.
3. If ADR-009's follow-up #1 (F.19-pre-b re-bench) triggers a planner-model change, `MODEL_ROUTER_CATALOG["planner"].canonical` moves under that superseding ADR; the compatible set is amended in the same slice.

## Lock-in phase

Stage 1 reconciliation-plan-v1, sub-slices 1.5.3–1.5.5. Lands on `slice/dual-mode-routing-adr` off `slice/stage1-reconciliation-v1`.

## References

- [ADR-009 — Local LLM Selection for Forge-OH F.19+](./009-local-llm-selection.md) — supersedes §1, §2, §3, §3a at routing-layer only.
- [`bff/services/model_router.py`](../../bff/services/model_router.py) — `route_by_role`, `RoleRoute`.
- [`bff/routers/runs.py::create_run`](../../bff/routers/runs.py) — `_resolve_role`, two-pass routing entry-point.
- [`bff/routers/agent_presets.py`](../../bff/routers/agent_presets.py) — target of §2–§4 changes.
- Reconciliation-plan-v1 §1.5.3–1.5.5 (operator's Stage 1 spec, attached to the session).
- SESSION_HANDOFF.md 2026-08-04 21:57 EDT — operator resolution to open question #1 (option b).
