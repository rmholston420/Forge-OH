# ADR-027: Runtime Model Switching — BFF forwards only `switch_llm`, blast-radius-minimized

- **Status:** Proposed
- **Date:** 2026-08-06
- **Slice:** Stage 6.5 · reconciliation-plan-stage-6 §6.5.2 (backend forwarding endpoint)
- **Supersedes:** —
- **Related:** [ADR-012 (dual-mode routing)](./012-dual-mode-model-routing.md), [ADR-013 (canonical coder + planner)](./013-qwen36-27b-canonical-coder-planner.md), Reconciliation-plan-stage-6 §6.5, [`DEBUG_LOG.md` 2026-08-06 09:43 EDT SDK gap check](../../DEBUG_LOG.md).

## Context

Reconciliation-plan-stage-6 §6.5.2 assumed **one** agent-server REST endpoint for runtime model switching, provisionally spelled `POST /api/conversations/{conversation_id}/switch-model` with body `{model, backendId}`. The §6.5.1 SDK gap check on Colossus against openhands-sdk==1.40.0 (verified 2026-08-06 09:43 EDT via `/openapi.json` fetch, 591 702 bytes) invalidated both the path and the single-endpoint assumption. The agent-server exposes **three** distinct switch routes, each with a different contract:

| Route | Body shape | Blast radius |
|-------|------------|--------------|
| `POST /api/conversations/{cid}/switch_profile` | `{profile_name: str}` | **Whole profile** — model + system prompt + tools + guardrails all mutate atomically. |
| `POST /api/conversations/{cid}/switch_llm` | `{llm: LLM-Input}` where `LLM-Input` carries `model`, `api_key`, `auth_type ∈ {api_key, subscription}`, `subscription_vendor`, `base_url`, and adapter-specific keys | LLM adapter only — model + credentials + base URL. System prompt, tool set, and ACP layer are untouched. |
| `POST /api/conversations/{cid}/switch_acp_model` | `{model: str}` | ACP (Agent Communication Protocol) negotiation layer only — does **not** change the primary LLM the agent invokes. |

Related read routes (also verified present): `GET /api/llm/models` (flat catalog) and `GET /api/llm/models/verified` (grouped by provider).

The plan's request shape `{model, backendId}` does not exist on any of the three variants. `switch_llm` demands a full `LLM-Input`; `switch_profile` demands a profile name; `switch_acp_model` accepts a bare model string but operates on the wrong layer.

The BFF must therefore choose which variant(s) to expose as its own `POST /api/runs/{run_id}/model` forwarding endpoint. This is a load-bearing port-contract decision — it dictates the frontend UX affordance, the preset↔model coupling, and the mid-conversation stability guarantees the operator receives when they invoke "switch model" during a live run.

## Decision

The Forge-OH BFF forwards **only `switch_llm`** in Stage 6.5.2. The other two agent-server variants (`switch_profile`, `switch_acp_model`) are deliberately not exposed by the BFF in this stage.

### 1. BFF endpoint contract

```
POST /api/runs/{run_id}/model
```

Request body (BFF-side):

```json
{
  "agentPresetId": "ap-1"
}
```

- Only `agentPresetId` is accepted. Raw model strings and free-form `LLM-Input` blobs are rejected with 422.
- The BFF resolves `agentPresetId` against `agent_presets._PRESETS`. If the preset is unknown, return 404.
- The BFF hydrates a full `LLM-Input` from the resolved preset — reading `model`, `base_url`, and credentials (from the secrets store, not the request body) — and posts it to agent-server as `{llm: LLM-Input}`.
- The BFF looks up the `conversation_id` for `run_id` via the existing run→conversation mapping (`bff/services/runs.py::get_conversation_id_for_run`; already used elsewhere) before issuing the upstream POST.

Response (BFF-side):

```json
{
  "ok": true,
  "run_id": "<id>",
  "conversation_id": "<id>",
  "agentPresetId": "ap-1",
  "resolved_model": "<model-name-hydrated-from-preset>",
  "resolved_base_url": "<base-url-hydrated-from-preset>",
  "agent_server_response": { "success": true }
}
```

422 on unknown preset, invalid role↔model coupling per ADR-012, or agent-server 422/5xx echo.

### 2. Preset-driven hydration (ADR-012 alignment)

The BFF MUST NOT accept a bare `model` string or an `LLM-Input` blob from the client. All model-switch traffic passes through the preset layer so:

- ADR-012 §1 (role-first routing with preset override) continues to hold mid-run: the preset's `model` still has to be a member of the resident role's `compatible_models` set per ADR-012 §3. If it is not, the BFF returns 422 with `preset_model_incompatible_for_role` and does not call agent-server.
- ADR-013 canonical coder/planner ratifications remain the fallback — the BFF's `route_by_role` catalog is the single source of truth for what constitutes a legal model.
- Credentials never live in the frontend or the request body. The frontend picks a preset ID; the BFF injects `api_key` from the secrets store at forward time.

### 3. What is explicitly NOT decided here

- **`switch_profile` is deferred.** A whole-profile mid-run swap changes the system prompt and tool set alongside the model, which is a semantically different UX ("switch agent", not "switch model") and warrants its own ADR + plan slice when the need arises. Not-now, not never.
- **`switch_acp_model` is deferred indefinitely.** Forge-OH does not surface an ACP-negotiated model separately from the primary LLM at this stage; exposing this endpoint would be a UI control with no user-visible effect (violates the same "no-dead-end" rule that governs §6.5.1).
- **Model catalog surfacing.** The BFF may expose `GET /api/llm/models[/verified]` as read-through routes in a follow-up slice, but Stage 6.5.2 as written does not require it — the preset catalog already gives the frontend everything it needs to render a picker.

## Rationale

Chosen over two alternatives:

- **A. Forward `switch_profile`.** Rejected — user-facing UX affordance is "switch model", not "switch agent". Silently mutating the system prompt mid-run violates the principle that mid-conversation actions should not surprise the operator. The whole-profile swap is a valid capability, but it belongs to a distinct future slice with its own frontend affordance and confirmation flow.
- **B. Forward `switch_acp_model`.** Rejected — wrong layer. It mutates the ACP negotiation model, not the primary LLM. Forge-OH does not currently expose ACP-level model choice, so a control forwarded here would be a UI element with no user-visible behavioral change on the primary agent — the exact anti-pattern the reconciliation-plan-stage-6 §6.5.1 warning quotes ("a UI control with no real backend effect is exactly as forbidden as a backend-only dead end").
- **C. (chosen) Forward `switch_llm` behind preset-driven hydration.** Matches the user's mental model ("switch model" ≡ swap the LLM), keeps credentials server-side, defers to ADR-012 for role↔model compatibility, and gives the smallest blast-radius change consistent with the plan's intent.

## Consequences

Files that change under Stage 6.5.2 (this ADR does not itself land the code — that is §6.5.2's job):

- `bff/routers/runs.py` — add `POST /api/runs/{run_id}/model` with the contract above.
- `bff/services/agent_server_client.py` (or equivalent forwarding surface — inspect before choosing exact filename) — add typed forwarder `switch_llm(conversation_id, llm_input)`.
- `bff/services/agent_presets.py` — add a helper to hydrate an `LLM-Input` payload from a preset ID + resolved secrets. Do not leak credentials into logs or error responses.
- `bff/services/model_router.py` — no logic change, but `MODEL_ROUTER_CATALOG` remains the compatibility oracle called from the switch endpoint.
- `bff/tests/test_runs_model_switch.py` (new) — pytest suite: unknown preset → 404, incompatible preset↔role → 422, happy path → 200 with agent-server `{success: true}` echo, agent-server 5xx echo → 502.
- Frontend §6.5.3 must not build a raw-model picker; it must be preset-driven.
- `DEBUG_LOG.md` (already updated 2026-08-06 09:43 EDT with the SDK gap check finding).
- `BUILD_LOG.md` — append entry when §6.5.2 lands.

Not affected by this ADR:

- Existing ADR-012 routing behavior for **new** runs — this ADR governs mid-run switching only. `create_run` continues to route per ADR-012 §1.
- ADR-013 canonical coder/planner ratifications.

## Lock-in phase

Ratifies when Stage 6.5.2 backend endpoint lands with green pytest suite AND the §6.5.3 frontend control lands preset-driven (not raw-model). Until then this ADR is Proposed.

## References

- Reconciliation-plan-stage-6 §6.5, §6.5.1 (SDK gap check), §6.5.2 (backend forwarding).
- [ADR-012](./012-dual-mode-model-routing.md) §1, §3 (role-first routing, compatible-model set).
- [ADR-013](./013-qwen36-27b-canonical-coder-planner.md) (canonical coder + planner).
- [`DEBUG_LOG.md` 2026-08-06 09:43 EDT](../../DEBUG_LOG.md) — verbatim SDK gap check output.
- openhands-sdk==1.40.0 agent-server `/openapi.json` (591 702 bytes, fetched from `http://127.0.0.1:8090/openapi.json` on Colossus 2026-08-06 09:43 EDT).
