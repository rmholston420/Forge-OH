# Forge-OH Session Handoff — 2026-08-04 22:04 EDT

## Current build-sequencing position
- **Stage / phase:** Stage 1 · reconciliation-plan-v1 · sub-slices 1.5.3–1.5.5 (ADR authored; implementation pending).
- **Slice branch:** `slice/dual-mode-routing-adr` (this slice, ADR-only) → will be followed by `slice/dual-mode-routing-impl` (implementation).
- **Base branch:** `slice/stage1-reconciliation-v1` (1.1–1.4, 1.5.2, 1.6, 1.7 landed there; awaiting Colossus verify + PR merge).
- **Plugin / kernel component:** BFF `model_router`, `agent_presets`, `create_run`; frontend `agent-presets` preset editor.
- **Port(s) in progress:** none new. ADR-012 preserves ADR-009 §3a dual-port + swap-on-demand supervisor topology (:8501 coder, :8511 planner).

## Completed this session
- Authored ADR-012 (dual-mode model routing) superseding ADR-009 §1/§2/§3/§3a at the routing-layer contract. Role-based routing remains canonical and takes precedence; preset-driven model override layers on top only when compatible with the resident role's model.
- Amended ADR-009 with a status-amendment block noting the partial supersede and cross-linking ADR-012.
- Created `docs/adr/README.md` ADR index.

## Remaining before current Definition of Done
Definition of Done for reconciliation-plan-v1 §1.5.3–1.5.5:

1. **ADR-012 landed** ✅ this slice.
2. **Implementation slice `slice/dual-mode-routing-impl` (next):**
   - `bff/services/model_router.py`: add `RoleCatalog`, `MODEL_ROUTER_CATALOG`, `ModelIncompatibleWithRoleError`, `resolve_preset_route(role, preset_model, context_length)` wrapper.
   - `bff/routers/agent_presets.py`: remove `ModelId` Literal; add `role` field; validate `model ∈ MODEL_ROUTER_CATALOG[role].compatible` at POST/PATCH; replace `_PRESETS` dict with SQLite store at `~/.forge-oh/agent_presets.db`; idempotent `CREATE TABLE IF NOT EXISTS`; seed on empty; unique-index-on-default.
   - `bff/routers/runs.py::create_run`: after `route_by_role`, look up preset; if `preset.model ∈ MODEL_ROUTER_CATALOG[role].compatible`, override `route.model`; else emit `preset_model_incompatible` sidecar event and proceed with canonical.
   - New `GET /api/agent-presets/catalog` endpoint exposing `MODEL_ROUTER_CATALOG`.
   - Frontend `src/features/agent-presets/*`: preset editor gains `role` selector; model dropdown filters by selected role via catalog endpoint.
   - Tests: `bff/tests/test_agent_presets_role_validation.py`, `bff/tests/test_dual_mode_routing.py`, `bff/tests/test_agent_presets_sqlite.py`.
3. **Colossus verify** (per operator directive #2): `pnpm typecheck && pnpm test:unit && pnpm build && pytest bff/tests/test_agent_presets_*.py bff/tests/test_dual_mode_routing.py`.

## Open questions / awaiting user answer
- **When to start `slice/dual-mode-routing-impl`?** Operator confirmed the ADR slice starts off `slice/stage1-reconciliation-v1`; implementation could either (a) branch off `slice/dual-mode-routing-adr` and stack, or (b) wait for both to merge into main and branch off main. Default: (a) stacking, so ADR-012 is visible in the implementation PR's diff-context.
- **Any operator preference on the `MODEL_ROUTER_CATALOG` compatible-set contents?** ADR-012 seeds:
  - `coder.compatible = {"qwen3.6-35b-nvfp4", "qwen3-coder:32k"}` (canonical + verified Ollama fallback from DEBUG_LOG 2026-08-04).
  - `planner.compatible = {"qwen3-thinking-2507-awq"}` (canonical only — ADR-009 §2/§4 rule out planner Ollama fallback).
  - Add anything?

## Exact next action
1. On Colossus: `git fetch origin && git checkout slice/dual-mode-routing-adr && git pull` to review the ADR.
2. If ADR-012 reads correctly and the compatible-set seed matches operator intent, say the word and I'll open `slice/dual-mode-routing-impl` off this branch and land the implementation.
3. Independently, the base `slice/stage1-reconciliation-v1` still awaits Colossus runtime verify + PR merge (pip-compile regen, `pnpm typecheck && pnpm test:unit && pnpm build`, Playwright, manual smokes).
