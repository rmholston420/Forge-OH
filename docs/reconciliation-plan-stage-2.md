
# Forge-OH Reconciliation Plan v1 — Stage 2 (Detailed, Amended)

> **Status:** Canonical Stage 2 execution plan.
> **Amended 2026-08-05 21:58 EDT** to match the live `bff/services/model_router.py`
> (dual vLLM roles :8501/:8511, `ops/vllm_supervisor.sh` swap-on-demand,
> `RoleRoute` dataclass, ADR-009 §3a topology). The v1 first-draft snippets
> that assumed a single-vLLM, Ollama-only router are superseded by this file.
> Preserves the Stage 2 **goal** verbatim; changes only the **implementation
> path**. See § "Reality delta" at the bottom for the exact deviations.

Standalone implementation plan for Perplexity Computer. Target: Colossus (128GB RAM, RTX 5090, 32GB VRAM, Blackwell SM_120). Single-user, local-first, no cloud control planes.

**Prerequisite:** Stage 1 complete AND F.3 SWE-bench Verified full-500 validation CLOSED (pass@1 = 26.6% on green Stage-1 `main` `530db1a`, per BUILD_LOG 2026-08-05 and ADR-013 amendment #2). Read `SESSION_HANDOFF.md` before starting — it should point here.

**Governing rule (non-negotiable):** backend and frontend ship together in the same commit/session. A backend endpoint with no reachable UI path, or a UI control wired to a stub, is not "done."

**Stage 2 goal (unchanged from v1 first draft):** replace Forge-OH's Ollama-only routing with a genuine `InferenceBackend` port supporting Ollama, vLLM, llama.cpp, and SGLang, each exposed as a health-checked, selectable adapter in the UI, with Colossus/Blackwell-specific tuning living entirely inside the adapters (never the routing core), and a VRAM-aware concurrency ceiling for future worktree-parallel agents.

**Stage 2 architectural invariant (new, load-bearing):**
`InferenceBackend` is a **health-inventory + selection layer above the
existing role-routing core**, not a replacement for it. `route_by_role()`
retains its role→backend→model→max_tokens resolution, swap-on-demand
supervisor coalescing, and Ollama fallback semantics. The four adapters
give the UI a live, health-checked view of every runtime the router
*could* route to, plus an optional `backendId` override on `POST /runs`
that pins a specific runtime for that run.

```bash
cd ~/dev/forge-oh
cat SESSION_HANDOFF.md
```

Confirm it names Stage 2 as the next action before proceeding.

---

## 2.0 Baseline inspection

```bash
cd ~/dev/forge-oh && git pull
head -80 bff/services/model_router.py
grep -n "route_by_role\|list_available_models\|BACKEND_REGISTRY" bff/services/model_router.py
grep -n "backend\|route_by_role\|RoleRoute" bff/routers/runs.py | head -40
grep -n "^AgentPreset\|ModelId\s*=\s*Literal" bff/routers/agent_presets.py
ls -la ops/vllm_supervisor.sh ops/vllm_launch_coder.sh ops/vllm_launch_planner.sh 2>/dev/null
nvidia-smi --query-gpu=name,memory.total,memory.used,compute_cap --format=csv
```

Record the exact current shape — every code snippet below is adapted to
the **live** file shape (as of `main` at F.3 close), not the illustrative
snippets in the v1 first draft.

**Do NOT delete or simplify:**

- `RoleRoute` dataclass (`role`, `backend`, `model`, `base_url`, `max_tokens`)
- `_supervisor_ensure()` per-role locks + request-cap discipline
- `_vllm_role_health()` `/v1/models` readiness probe (not `/health`)
- Ollama fallback logic (coder-only by default; planner `""` = disabled)
- `VLLM_SUPERVISOR_REQUEST_CAP` short-circuit — G.1 fix, do not undo
- `_LEGACY_TASK_TO_ROLE` mapping in `bff/routers/settings.py`

Every code path above is protected by tests and by ADR-009 §3a. Any
edit that changes them requires a new ADR.

---

## 2.1 Backend — `InferenceBackend` protocol (health-inventory layer)

### 2.1.1 Package layout + protocol

```bash
mkdir -p bff/services/inference_backends
touch bff/services/inference_backends/__init__.py
```

```python
# bff/services/inference_backends/types.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel


class HealthStatus(str, Enum):
    CONNECTED = "connected"
    WARNING = "warning"
    DISCONNECTED = "disconnected"


class BackendHealth(BaseModel):
    status: HealthStatus
    latency_ms: float | None = None
    error: str | None = None


class ModelInfo(BaseModel):
    tag: str
    context_length: int | None = None
    quant: str | None = None
    size_bytes: int | None = None
```

```python
# bff/services/inference_backends/protocol.py
from __future__ import annotations
from typing import Protocol, runtime_checkable
from .types import BackendHealth, ModelInfo


@runtime_checkable
class InferenceBackend(Protocol):
    id: str
    display_name: str
    base_url: str

    async def health_check(self) -> BackendHealth: ...
    async def list_models(self) -> list[ModelInfo]: ...

    @property
    def supports_streaming(self) -> bool: ...
```

### 2.1.2 Adapter set — six adapters, not four

Colossus's live vLLM topology is dual-role (coder + planner). Registry
holds **six** entries so the UI can show the real fleet:

| id             | class            | default base_url                | notes                                          |
|----------------|------------------|---------------------------------|------------------------------------------------|
| `ollama`       | `OllamaBackend`  | `http://localhost:11434`        | Existing primary — same probe as `ollama_health_check` |
| `vllm-coder`   | `VLLMBackend`    | `http://localhost:8501`         | Live under supervisor (ADR-009 §3a)            |
| `vllm-planner` | `VLLMBackend`    | `http://localhost:8511`         | Live under supervisor (ADR-009 §3a); note: coder/planner cannot be co-resident on the 5090 — supervisor swaps |
| `vllm-legacy`  | `VLLMBackend`    | `http://localhost:8500`         | F.18 legacy probe surface — retained for settings display parity; `disabled_by_default=true` |
| `llamacpp`     | `LlamaCppBackend`| `http://localhost:8080`         | Not deployed on Colossus yet; adapter must return `disconnected` cleanly |
| `sglang`       | `SGLangBackend`  | `http://localhost:30000/v1`     | Not deployed on Colossus yet; adapter must return `disconnected` cleanly |

Adapters reuse existing probe patterns:

- Ollama: `GET {base_url}/api/tags` → 200 + non-empty `models[]`
- vLLM (all three role variants): `GET {base_url}/v1/models` → 200 + non-empty `data[]` (mirrors `_vllm_role_health`)
- llama.cpp: `GET {base_url}/health` → 200; `list_models` from `{base_url}/v1/models` best-effort
- SGLang: `GET {base_url}/v1/models` → 200 + non-empty `data[]`

Each adapter is a thin `httpx.AsyncClient` call with a 3.0s timeout and
returns `BackendHealth(status=DISCONNECTED, error=str(e))` on any
exception — no silent failures.

### 2.1.3 Registry

```python
# bff/services/inference_backends/registry.py
from __future__ import annotations
import os
from .ollama_backend import OllamaBackend
from .vllm_backend import VLLMBackend
from .llamacpp_backend import LlamaCppBackend
from .sglang_backend import SGLangBackend


def build_registry() -> dict[str, object]:
    return {
        "ollama": OllamaBackend(
            id="ollama",
            display_name="Ollama",
            base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ),
        "vllm-coder": VLLMBackend(
            id="vllm-coder",
            display_name="vLLM (coder)",
            base_url=os.getenv("LLM_CODER_URL", "http://localhost:8501"),
        ),
        "vllm-planner": VLLMBackend(
            id="vllm-planner",
            display_name="vLLM (planner)",
            base_url=os.getenv("LLM_PLANNER_URL", "http://localhost:8511"),
        ),
        "vllm-legacy": VLLMBackend(
            id="vllm-legacy",
            display_name="vLLM (legacy F.18 probe)",
            base_url=os.getenv("VLLM_URL", "http://localhost:8500"),
        ),
        "llamacpp": LlamaCppBackend(
            id="llamacpp",
            display_name="llama.cpp",
            base_url=os.getenv("LLAMACPP_BASE_URL", "http://localhost:8080"),
        ),
        "sglang": SGLangBackend(
            id="sglang",
            display_name="SGLang",
            base_url=os.getenv("SGLANG_BASE_URL", "http://localhost:30000/v1"),
        ),
    }


BACKEND_REGISTRY: dict[str, object] = build_registry()
```

New env vars added to `.env.example`: `LLAMACPP_BASE_URL`, `SGLANG_BASE_URL`.
Existing `OLLAMA_URL`, `LLM_CODER_URL`, `LLM_PLANNER_URL`, `VLLM_URL`
are reused unchanged.

### 2.1.4 Router endpoint — `GET /api/inference-backends`

```python
# bff/routers/inference_backends.py
from __future__ import annotations
from fastapi import APIRouter
from bff.services.inference_backends.registry import BACKEND_REGISTRY

router = APIRouter(prefix="/api/inference-backends", tags=["inference-backends"])


@router.get("")
async def list_inference_backends() -> dict:
    results = []
    for backend_id, backend in BACKEND_REGISTRY.items():
        health = await backend.health_check()
        results.append({
            "id": backend_id,
            "displayName": backend.display_name,
            "baseUrl": backend.base_url,
            "health": health.model_dump(),
            "supportsStreaming": backend.supports_streaming,
        })
    return {"backends": results}
```

Register in `bff/main.py` alongside existing routers:

```python
# bff/main.py — add to the imports and app.include_router calls
from bff.routers import inference_backends
# ... existing includes ...
app.include_router(inference_backends.router)
```

**Do NOT change** `bff/services/model_router.py`'s `route_by_role`
signature or behavior in this substage.

### 2.1.5 `route_by_role` — additive extension only

`route_by_role(role: str, context_length: int = 0)` keeps its current
signature. A new **optional** parameter is appended:

```python
# bff/services/model_router.py — signature change only
async def route_by_role(
    role: str,
    context_length: int = 0,
    backend_id: str | None = None,  # NEW: optional override
) -> RoleRoute:
```

Semantics when `backend_id` is:

- `None` (default) → **existing behavior unchanged**: probe role URL → supervisor ensure → Ollama fallback.
- `"ollama"` → skip vLLM entirely; route to `ollama_fallback` model. Raise `ModelUnavailableError` if the role has no Ollama fallback (planner).
- `"vllm-coder"` / `"vllm-planner"` → skip supervisor if role mismatches (e.g. `role="coder"` + `backend_id="vllm-planner"` returns planner URL/model). Probe the requested role URL directly; if down, raise `ModelUnavailableError` (do NOT invoke supervisor, do NOT fall back to Ollama — explicit selection means user wants that runtime or nothing).
- `"llamacpp"` / `"sglang"` → raise `ModelUnavailableError("backend {id} not yet routable")` for Stage 2. Stage 2 gives them health visibility only; wiring their `RoleRoute` construction lands in a Stage 2 follow-up once Colossus actually runs one.
- `"vllm-legacy"` → raise `ModelUnavailableError("vllm-legacy is probe-only")`. This backend appears in the health surface but is not a routing target.

Tests to add (all under `bff/tests/services/test_model_router.py`):

- `test_route_by_role_default_unchanged` — pin existing behavior with no `backend_id`.
- `test_route_by_role_explicit_ollama_coder` — routes to Ollama fallback, skips vLLM probe.
- `test_route_by_role_explicit_vllm_coder_skips_supervisor` — mock supervisor to raise if called.
- `test_route_by_role_llamacpp_raises` — future adapter guard.
- `test_route_by_role_vllm_legacy_raises` — probe-only guard.
- `test_route_by_role_planner_ollama_raises` — planner has no Ollama fallback.

### 2.1.6 `POST /runs` — thread `backendId` through

```bash
grep -n "class CreateRunRequest" bff/routers/runs.py
```

Add `backendId: str | None = None` to `CreateRunRequest`. In the run
creation path where `route_by_role` is currently called, forward it:

```python
# bff/routers/runs.py — inside create_run, where route_by_role is called
route = await route_by_role(
    role=resolved_role,
    context_length=context_length,
    backend_id=payload.backendId,
)
```

The response's `routing` block already carries `backend` + `model` +
`base_url` from `RoleRoute` — that field satisfies the plan's "confirm
`routing` block shows the preset's backend" verification without a new
response field.

### 2.1.7 `AgentPreset` — replace cloud `Literal` with real local tags

This resolves the KNOWN_ISSUES entry the SESSION_HANDOFF flagged
("agent-preset `ModelId` static Literal").

```python
# bff/routers/agent_presets.py — replace lines defining ModelId + AgentPreset.model
from bff.services.model_router import (
    LLM_CODER_MODEL,
    LLM_PLANNER_MODEL,
    LLM_CODER_OLLAMA_FALLBACK,
    FAST_MODEL,
    PRIMARY_MODEL,
    ALT_MODEL,
    VLLM_FALLBACK_MODEL,
)

# ModelId is no longer a static Literal — it is a free-form string,
# validated at run creation via route_by_role() against the live registry.
# The static list of "known good" tags below is used only to seed the UI
# picker; unknown tags are accepted at the API layer (users may add local
# GGUFs). Contract: any tag accepted here must resolve to a real endpoint
# via bff/services/model_router.py or the run creation will fail cleanly
# with ModelUnavailableError.

class AgentPreset(BaseModel):
    id: str
    name: str
    description: str | None = None
    systemPrompt: str = ""
    model: str = LLM_CODER_MODEL  # free-form; validated at run creation
    backendId: str | None = None  # NEW: optional pin ("vllm-coder", "ollama", ...)
    role: str = "coder"           # NEW: "coder" | "planner"
    maxSteps: int = 100
    maxCost: float = 5.0
    temperature: float = 0.2
    topP: float = 0.95
    toolAllowlist: list[str] = []
    loopGuard: LoopGuardConfig = Field(default_factory=LoopGuardConfig)
    isDefault: bool = False
    createdAt: str
    updatedAt: str
```

`CreateRequest` / `UpdateRequest` gain the same `backendId: str | None`
and `role: str` fields.

Seed data — replace `_PRESETS` in `bff/routers/agent_presets.py`:

```python
_PRESETS: dict[str, AgentPreset] = {
    "ap-1": AgentPreset(
        id="ap-1",
        name="Coder (c01 canonical)",
        description=(
            "Qwen3.6-27B INT4 AutoRound on vLLM coder role. F.3 SWE-bench "
            "Verified pass@1 = 26.6% (ADR-013 amendment #2, 2026-08-05)."
        ),
        systemPrompt="You are an expert software engineer. Think step by step.",
        model=LLM_CODER_MODEL,       # qwen3.6-27b-int4-autoround
        backendId="vllm-coder",
        role="coder",
        maxSteps=150,
        maxCost=8.0,
        isDefault=True,
        toolAllowlist=["filesystem", "bash", "browser"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(),
        updatedAt=_now(),
    ),
    "ap-2": AgentPreset(
        id="ap-2",
        name="Planner (DSR1-Distill-32B AWQ)",
        description=(
            "DeepSeek-R1-Distill-32B AWQ on vLLM planner role. ADR-013: "
            "beat c04 within tie window, ~4x faster."
        ),
        systemPrompt="You are a senior software architect. Plan carefully before acting.",
        model=LLM_PLANNER_MODEL,     # deepseek-r1-distill-32b-awq
        backendId="vllm-planner",
        role="planner",
        maxSteps=100,
        maxCost=8.0,
        isDefault=False,
        toolAllowlist=["filesystem", "bash", "browser"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(),
        updatedAt=_now(),
    ),
    "ap-3": AgentPreset(
        id="ap-3",
        name="Ollama coder fallback",
        description="qwen3-coder:32k on local Ollama. Use when vLLM is down.",
        systemPrompt="You are an expert software engineer.",
        model=LLM_CODER_OLLAMA_FALLBACK,  # qwen3-coder:32k
        backendId="ollama",
        role="coder",
        maxSteps=150,
        maxCost=8.0,
        isDefault=False,
        toolAllowlist=["filesystem", "bash", "browser"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(),
        updatedAt=_now(),
    ),
}
```

**Deferred to Stage 2 follow-up (not blocking exit gate):** persistence of
`_PRESETS` in SQLite (Stage 1.5 leftover). Handoff to Stage 3 will file
this in KNOWN_ISSUES if not landed by Stage 2 close.

### 2.1.8 `agentPresetId` on run records

Resolves the second KNOWN_ISSUES entry the handoff flagged. In
`bff/routers/runs.py`:

- Ensure `RunSummary` (or the equivalent response model) surfaces
  `agentPresetId` (the raw value from `CreateRunRequest`).
- In `create_run`, look up the preset by id **before** calling
  `route_by_role`, and use the preset's `role`, `model`, and `backendId`
  to drive the routing call. If `payload.backendId` is set on the run,
  it overrides the preset's `backendId` (per-run override).
- Persist the resolved `agentPresetId` alongside the run so `GET /runs/{id}`
  returns it (current code returns `None`).

Because Forge-OH's run store is `run_id == conversation_id` with no
SQLite mapping layer (per `runs.py` module docstring), the preset id
is threaded via agent-server conversation metadata, not a new DB
table. If that channel is not available at pinned SDK 1.40.0, keep a
minimal in-memory `dict[run_id, preset_id]` in the runs router and
document the persistence gap in KNOWN_ISSUES for Stage 3.

### 2.1.9 Verify — backend half

```bash
cd ~/dev/forge-oh
bash scripts/forge-restart.sh --bff-only
sleep 3
curl -s http://127.0.0.1:8081/api/inference-backends | python3 -m json.tool
```

Expected: six entries. On a Colossus with Ollama running and one vLLM
role live (say coder), that role reports `connected`; the other
vLLM role, `vllm-legacy`, `llamacpp`, and `sglang` all report
`disconnected` with a real `error` string (connection refused).

```bash
curl -s -X POST http://127.0.0.1:8081/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"title":"stage2 probe","agentPresetId":"ap-1","workspaceId":"18c99443b23c452899010095abd5f29b","backendId":"ollama","taskPrompt":"print hello"}' \
  | python3 -m json.tool
```

Confirm the response's `routing.backend == "ollama"` (override honored)
and `routing.model == "qwen3-coder:32k"` (the preset's Ollama-fallback
model, forced by the `backendId=ollama` override).

```bash
pytest bff/tests/services/test_model_router.py -q
pytest bff/tests/routers/test_inference_backends.py -q   # new file
pytest bff/tests/routers/test_agent_presets.py -q
pytest bff/tests/routers/test_runs.py -q
```

All green before proceeding.

---

## 2.2 Frontend — backend selector + live health

### 2.2.1 Reuse the existing MCP badge class-set

`src/features/mcp/McpServerCard.tsx` already defines the canonical
badge classes: `badge`, `badge--success`, `badge--warning`,
`badge--muted`, `badge--error`. The plan's v1 first draft proposed a
new `HealthBadge` component with Tailwind `bg-*-500` classes — that
does NOT match the codebase. Reuse the CSS-class pattern.

```typescript
// src/components/HealthBadge.tsx (new — reuses existing CSS classes)
type Status = 'connected' | 'warning' | 'disconnected';

const CLASSES: Record<Status, string> = {
  connected:    'badge badge--success',
  warning:      'badge badge--warning',
  disconnected: 'badge badge--muted',
};

export function HealthBadge({ status, label }: { status: Status; label?: string }) {
  return <span className={CLASSES[status]}>{label ?? status}</span>;
}
```

No refactor of `McpServerCard.tsx` in this stage — it uses the same
classes inline, and touching it invites regression risk on unrelated
MCP paths. Extract-on-second-use rule.

### 2.2.2 Confirm data-fetching library

```bash
grep -n "useQuery\|@tanstack/react-query\|useSWR" src/features/mcp/hooks.ts src/features/agent-presets/hooks.ts
```

Match whichever the codebase already uses (verified next). Snippets
below assume `@tanstack/react-query` per the v1 draft; if the repo
uses SWR instead, adapt at implementation time — API shape is
identical.

### 2.2.3 API client + hook

```typescript
// src/features/inference-backends/api.ts (new)
import { BASE } from '@/lib/api-base';   // match existing base-url import pattern

export interface InferenceBackendInfo {
  id: string;
  displayName: string;
  baseUrl: string;
  health: {
    status: 'connected' | 'warning' | 'disconnected';
    latency_ms?: number | null;
    error?: string | null;
  };
  supportsStreaming: boolean;
}

export async function fetchInferenceBackends(): Promise<InferenceBackendInfo[]> {
  const res = await fetch(`${BASE}/api/inference-backends`);
  if (!res.ok) throw new Error(`Failed to fetch inference backends: ${res.status}`);
  const data = await res.json();
  return data.backends;
}
```

```typescript
// src/features/inference-backends/hooks.ts (new)
import { useQuery } from '@tanstack/react-query';
import { fetchInferenceBackends } from './api';

export function useInferenceBackends() {
  return useQuery({
    queryKey: ['inference-backends'],
    queryFn: fetchInferenceBackends,
    refetchInterval: 10_000,
  });
}
```

### 2.2.4 `BackendSelector` component

```typescript
// src/features/inference-backends/BackendSelector.tsx (new)
'use client';
import { useInferenceBackends } from './hooks';
import { HealthBadge } from '@/components/HealthBadge';

export function BackendSelector({
  value,
  onChange,
  allowedIds,          // optional filter — e.g. presets scoped to vLLM only
}: {
  value: string | null;
  onChange: (id: string | null) => void;
  allowedIds?: string[];
}) {
  const { data: backends, isLoading } = useInferenceBackends();
  if (isLoading) return <div className="text-sm text-muted">Loading backends…</div>;
  const list = (backends ?? []).filter(b => !allowedIds || allowedIds.includes(b.id));

  return (
    <div className="backend-selector">
      <label>
        <input
          type="radio"
          name="backend"
          checked={value === null}
          onChange={() => onChange(null)}
        />
        Auto (route by role)
      </label>
      {list.map(b => (
        <label key={b.id} className={b.health.status === 'disconnected' ? 'opacity-60' : ''}>
          <input
            type="radio"
            name="backend"
            value={b.id}
            checked={value === b.id}
            disabled={b.health.status === 'disconnected'}
            onChange={() => onChange(b.id)}
          />
          <span>{b.displayName}</span>
          <HealthBadge status={b.health.status} />
          {b.health.latency_ms !== null && b.health.latency_ms !== undefined && (
            <span className="text-xs text-muted">{Math.round(b.health.latency_ms)}ms</span>
          )}
          {b.health.error && (
            <span className="text-xs text-error" title={b.health.error}>error</span>
          )}
        </label>
      ))}
    </div>
  );
}
```

Radio group (not `<select>`) because the plan requires per-item health
badges and disabled visual state — a native `<option>` can't render
badges cross-browser.

### 2.2.5 Wire into Agent Presets editor

```bash
find src/features/agent-presets -type f -name '*.tsx' | xargs grep -l 'form\|editor\|drawer' 2>/dev/null
```

Locate the actual preset-edit drawer/form component (name TBD until we
inspect). Add three controls:

1. **Role radio** — `coder` / `planner` (defaults to `coder`).
2. **`BackendSelector`** — bound to `preset.backendId`.
3. **Model text input** — free-form; placeholder text lists the router's
   known tags (`LLM_CODER_MODEL`, `LLM_PLANNER_MODEL`,
   `LLM_CODER_OLLAMA_FALLBACK`, etc.), read from a small
   `/api/inference-backends/known-models` helper if desirable, or hardcoded
   for Stage 2. Validation happens at run creation via `route_by_role`.

### 2.2.6 Wire into run-creation form

```bash
find src -type f -name '*.tsx' | xargs grep -l 'agentPresetId\|CreateRun\|newRun' 2>/dev/null
```

Add the `BackendSelector` (with `value=null` = "use preset") beneath the
existing preset picker. Selecting an entry sets `payload.backendId`; the
"Auto" radio leaves it unset. Value stored in the run-creation form
state; POSTed to `/api/runs` as `backendId`.

### 2.2.7 Verify — frontend half

```bash
cd ~/dev/forge-oh
bash scripts/forge-restart.sh
sleep 6
```

Navigate to `/agent-presets`:
- New/edit preset drawer shows role, backend selector, and model input.
- Selector shows six entries with live badges.

Navigate to run creation:
- Backend selector appears; "Auto" default is selected.
- Selecting `ollama` and creating a run → response body's `routing.backend == "ollama"`.

Playwright:
```bash
cd ~/dev/forge-oh/src
PLAYWRIGHT_FRONTEND_URL=http://127.0.0.1:3100 \
  npx playwright test tests/e2e/inference-backends.spec.ts --reporter=list
```

Spec (new): `tests/e2e/inference-backends.spec.ts` — screenshots the
selector on both pages, asserts `aria-label` on badges, waits for a
live health tick.

### 2.2.8 Log

```bash
cat >> BUILD_LOG.md << EOF

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 2.1–2.2: InferenceBackend port + selector shipped
- Backend: added InferenceBackend protocol + six adapters (ollama, vllm-coder, vllm-planner, vllm-legacy, llamacpp, sglang), registry, GET /api/inference-backends, backendId threaded through POST /runs + route_by_role (additive; existing role-based routing preserved per ADR-009 §3a).
- Backend: AgentPreset.model widened from cloud Literal to free-form string; added backendId + role fields; seeded ap-1 (coder canonical c01), ap-2 (planner canonical DSR1-Distill-32B AWQ), ap-3 (Ollama coder fallback). agentPresetId now driven end-to-end (resolves KNOWN_ISSUES pair).
- Frontend: HealthBadge (reuses existing badge CSS classes), BackendSelector radio group with live health, wired into Agent Presets editor and run-creation form.
- Files touched (backend): bff/services/inference_backends/{__init__.py,types.py,protocol.py,ollama_backend.py,vllm_backend.py,llamacpp_backend.py,sglang_backend.py,registry.py}, bff/services/model_router.py (additive), bff/routers/inference_backends.py, bff/routers/runs.py, bff/routers/agent_presets.py, bff/main.py, .env.example.
- Files touched (frontend): src/components/HealthBadge.tsx, src/features/inference-backends/{api.ts,hooks.ts,BackendSelector.tsx}, src/features/agent-presets/<editor>, src/app/(dashboard)/runs/new/<form>.
- Tests: bff/tests/routers/test_inference_backends.py (new), bff/tests/services/test_model_router.py (extended: 6 new cases), src/tests/e2e/inference-backends.spec.ts (new).
- Verification: /api/inference-backends returns six real entries with live health; POST /runs with backendId=ollama honored; ADR-009 §3a swap-on-demand unchanged.
- Both halves shipped together: yes.
EOF
```

Commit + push as Perplexity Computer per the slice-driver contract.

---

## 2.3 Colossus adapter tuning (Blackwell SM_120) — documentation-only in Stage 2

The v1 first draft asked for from-source builds of llama.cpp, vLLM, and
SGLang in this stage. Colossus already runs vLLM under the launcher
scripts, and llama.cpp / SGLang are not yet deployed. Stage 2's job is
**not** to deploy them — it is to make the adapter set future-ready and
to document the exact flags Colossus will need when they land.

### 2.3.1 Create `docs/colossus-inference-setup.md`

Single file capturing the Blackwell-specific incantations, cross-linked
from `bff/services/inference_backends/README.md` (new, one-page).
Contents (verbatim from v1 draft; unchanged):

- **llama.cpp** — `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="120" -DGGML_CUDA_FA_ALL_QUANTS=ON`; CUDA 12.8+ (13.2 recommended, cuDNN 9.20).
- **vLLM** — `TORCH_CUDA_ARCH_LIST="12.0"`, PyTorch cu128/cu130, `VLLM_ATTENTION_BACKEND=FLASHINFER` (never `flash-attn` — `undefined symbol` on SM_120). Note that Colossus's current F.19 topology uses the pinned `vllm/vllm-openai:v0.10.2` Docker image (already Blackwell-tuned); the from-source path is only if we ever leave the image.
- **SGLang** — standard install; verify `torch.cuda.get_device_capability() == (12, 0)`.

### 2.3.2 No new builds

**Do NOT build llama.cpp or SGLang on Colossus in this stage.** Skill
`forge-oh-llm-serving` is explicit: only one runtime holds the 5090 at
a time; the current F.3-validated topology is Ollama + vLLM-under-
supervisor. Introducing a llama.cpp build without an ADR breaks that
invariant.

If a future ADR opens llama.cpp / SGLang deployment on Colossus, the
adapter side is already ready — that ADR only needs to add a launcher
under `ops/` and flip `LLAMACPP_BASE_URL` / `SGLANG_BASE_URL` in `.env`
to a live port.

### 2.3.3 Log

```bash
cat >> BUILD_LOG.md << EOF

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 2.3: Colossus SM_120 flag matrix documented
- docs/colossus-inference-setup.md added (llama.cpp + vLLM + SGLang Blackwell flags).
- bff/services/inference_backends/README.md added (registry overview + link to setup doc).
- No runtime changes — Colossus's live topology (Ollama + vLLM-under-supervisor per ADR-009 §3a) unchanged.
- Verification: docs render; adapter registry unaffected.
EOF
```

---

## 2.4 VRAM-aware quant/concurrency budget

Uses the plan's original 2.4 approach — unchanged from v1 first draft
because Colossus doesn't yet have any of this logic and it doesn't
conflict with existing code.

### 2.4.1 Hardware detection helper

```python
# bff/services/inference_backends/hardware.py
from __future__ import annotations
import subprocess


def get_gpu_vram_mb() -> int | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return int(r.stdout.strip().split("\n")[0])
    except Exception:
        return None


def get_gpu_compute_capability() -> tuple[int, int] | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        major, minor = r.stdout.strip().split("\n")[0].split(".")
        return (int(major), int(minor))
    except Exception:
        return None
```

### 2.4.2 Deterministic quant-tier selector

```python
# bff/services/inference_backends/quant_selector.py
from __future__ import annotations
from .hardware import get_gpu_vram_mb


def recommend_quant_tier(model_param_count_b: float) -> str:
    vram_mb = get_gpu_vram_mb()
    if vram_mb is None:
        return "cpu-gguf-q4"
    vram_gb = vram_mb / 1024
    if model_param_count_b <= 32 and vram_gb >= 24:
        return "q8-full-context"
    if model_param_count_b >= 70:
        if vram_gb >= 32:
            return "iq3-8k-context"
        return "q4_k_m-partial-offload"
    return "q8-full-context"
```

Deterministic lookup, not an LLM judgment.

### 2.4.3 Concurrency ceiling

```python
# bff/services/inference_backends/concurrency.py
from __future__ import annotations
from .hardware import get_gpu_vram_mb


def max_concurrent_agents(
    base_model_footprint_mb: int,
    kv_cache_per_request_mb: int,
    reserved_headroom_mb: int = 4096,
) -> int:
    vram_mb = get_gpu_vram_mb()
    if vram_mb is None:
        return 1
    available = vram_mb - base_model_footprint_mb - reserved_headroom_mb
    if available <= 0:
        return 1
    return max(1, available // kv_cache_per_request_mb)
```

### 2.4.4 Endpoint

```python
# bff/routers/inference_backends.py — add
from bff.services.inference_backends.concurrency import max_concurrent_agents


@router.get("/concurrency-limit")
async def get_concurrency_limit(
    base_model_footprint_mb: int = 20000,
    kv_cache_per_request_mb: int = 1500,
) -> dict:
    return {
        "maxConcurrentAgents": max_concurrent_agents(
            base_model_footprint_mb, kv_cache_per_request_mb
        )
    }
```

### 2.4.5 Frontend — read-only display

```typescript
// src/features/settings/ConcurrencyLimitDisplay.tsx (new)
'use client';
import { useQuery } from '@tanstack/react-query';
import { BASE } from '@/lib/api-base';

export function ConcurrencyLimitDisplay() {
  const { data } = useQuery({
    queryKey: ['concurrency-limit'],
    queryFn: async () => {
      const res = await fetch(`${BASE}/api/inference-backends/concurrency-limit`);
      return res.json();
    },
  });
  return (
    <div className="setting-row">
      <span>Estimated max concurrent agents on this GPU:</span>
      <span className="badge badge--muted">{data?.maxConcurrentAgents ?? '…'}</span>
    </div>
  );
}
```

Add to the Settings page (existing `/settings` route). Deliberately
minimal — worktree-parallel orchestration UI belongs to whichever
later stage implements it.

### 2.4.6 Verify

```bash
curl -s "http://127.0.0.1:8081/api/inference-backends/concurrency-limit?base_model_footprint_mb=20000&kv_cache_per_request_mb=1500"
```

On Colossus's 32GB card: expect a small positive integer (4–8), not 0
or an absurdly large number.

### 2.4.7 Log

```bash
cat >> BUILD_LOG.md << EOF

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 2.4: VRAM-aware quant/concurrency budget shipped
- Backend: hardware.py (nvidia-smi VRAM/compute_cap query), quant_selector.py (deterministic tier lookup), concurrency.py (runtime-computed ceiling), GET /api/inference-backends/concurrency-limit.
- Frontend: ConcurrencyLimitDisplay read-only indicator on /settings.
- Files touched (backend): bff/services/inference_backends/{hardware.py,quant_selector.py,concurrency.py}, bff/routers/inference_backends.py.
- Files touched (frontend): src/features/settings/ConcurrencyLimitDisplay.tsx.
- Verification: concurrency-limit endpoint returns plausible integer on Colossus 32GB card; frontend renders it.
- Both halves shipped together: yes (deliberately minimal — worktree-orchestration UI deferred).
EOF
```

---

## Stage 2 exit gate — do not advance to Stage 3 until all pass

```bash
cd ~/dev/forge-oh
pytest bff/tests/ -q
pnpm typecheck
pnpm test:unit
pnpm build
```

Manual verification checklist:

- [ ] `GET /api/inference-backends` returns six entries with real live health.
- [ ] Starting Ollama alone shows only `ollama` connected; the rest disconnected with a real `error` string (not silent).
- [ ] Starting the supervisor's coder role shows `vllm-coder` connected within one poll interval (10s).
- [ ] Swapping to planner via `bash ops/vllm_supervisor.sh ensure planner` shows `vllm-planner` connected, `vllm-coder` disconnected (ADR-009 §3a topology honored — one-at-a-time).
- [ ] Agent Presets editor shows role radio, backend selector, and model input; three seed presets (ap-1 coder, ap-2 planner, ap-3 Ollama-fallback) render.
- [ ] Run-creation form's backend selector defaults to "Auto"; picking `ollama` on a coder preset routes to `qwen3-coder:32k`, and the response's `routing.backend == "ollama"`.
- [ ] Run with `backendId=vllm-coder` when only planner is live returns `blocked` status with `ModelUnavailableError` reason (explicit selection = no supervisor swap, no Ollama fallback).
- [ ] `GET /runs/{id}` returns non-null `agentPresetId` (resolves KNOWN_ISSUES entry).
- [ ] `docs/colossus-inference-setup.md` present with SM_120 flag matrix.
- [ ] `GET /api/inference-backends/concurrency-limit` returns plausible integer on 32GB card; Settings page displays it.
- [ ] F.3 SWE-bench Verified smoke re-run (5-task subset, not full 500) matches previous pass rate — additive backendId did not regress role-based routing.

## Final Stage 2 log entry

```bash
cat >> BUILD_LOG.md << EOF

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 2 COMPLETE
- All Stage 2 exit-gate checks passed.
- InferenceBackend port live with six adapters; ADR-009 §3a swap-on-demand preserved; agentPresetId end-to-end resolved.
- VRAM-aware concurrency ceiling computed and surfaced.
- Next action: begin Stage 3.1 (Security Analyzer risk indicators — confirm openhands-sdk 1.40.0 exposes risk_level on ActionEvent).
EOF

cat > SESSION_HANDOFF.md << EOF
# Session Handoff

**Current stage:** Stage 2 complete, ready to begin Stage 3 (Security, Risk, and Approval Maturity).

**Completed this session:**
- Stage 2.1–2.4, all verified per exit-gate checklist.
- Two KNOWN_ISSUES entries resolved: (1) AgentPreset.ModelId static Literal → free-form string with backendId+role fields; (2) agentPresetId now persisted and surfaced on run records.

**Remaining before Stage 2 Definition of Done:** none — Stage 2 is fully complete.

**Open questions awaiting review:** none outstanding from Stage 2. AgentPreset SQLite persistence still deferred (Stage 1.5 leftover) — filed in KNOWN_ISSUES for pickup in Stage 3.

**Exact next action:** Begin Stage 3.1 — confirm whether pinned openhands-sdk==1.40.0 exposes security-analyzer risk_level on ActionEvents; if present, surface it in bff/services/event_normalize.py and add a risk badge to the event timeline.
EOF
```

---

## Reality delta — what this amended plan changes vs the v1 first draft

Recorded for audit trail. All deviations are conservative (preserve
what works, extend cleanly).

| v1 first draft assumed | Live reality | Amended path |
|---|---|---|
| Single vLLM at `http://localhost:8001/v1` | Dual roles `:8501` coder + `:8511` planner + F.18 legacy `:8500`, swap-on-demand via `ops/vllm_supervisor.sh` (ADR-009 §3a) | Registry has **six** adapters: `ollama`, `vllm-coder`, `vllm-planner`, `vllm-legacy`, `llamacpp`, `sglang` |
| `route_by_role(role, model, backend_id)` — a rewrite | `route_by_role(role, context_length=0)` returning `RoleRoute` with supervisor coalescing + Ollama fallback | Additive: new optional `backend_id: str \| None = None` param. Default behavior unchanged. Explicit ids get new dispatch logic |
| Plan installs and configures llama.cpp / vLLM / SGLang builds on Colossus | Colossus runs pinned `vllm/vllm-openai:v0.10.2` Docker image; llama.cpp / SGLang not deployed | Stage 2 = adapters + docs only. Build/deploy of llama.cpp / SGLang deferred to a future ADR (adapter side ready to go the day it lands) |
| New Tailwind `HealthBadge` | Codebase uses CSS classes `badge badge--success/warning/muted/error` | `HealthBadge` reuses existing classes; no design-system change |
| `<select>` with disabled `<option>` | Native `<option>` can't render badges cross-browser | Radio group with per-item `HealthBadge` |
| SQLite `_PRESETS` persistence | Was Stage 1.5 deliverable, still in-memory | Deferred; filed in KNOWN_ISSUES. Not blocking Stage 2 exit gate |
| No mention of AgentPreset `Literal` fix | KNOWN_ISSUES flags cloud `Literal` still live on `main` | Rolled into 2.1.7 (SESSION_HANDOFF instruction) |
| No mention of `agentPresetId` null on runs | KNOWN_ISSUES flags `agentPresetId: null` in responses | Rolled into 2.1.8 (SESSION_HANDOFF instruction) |

Every code snippet in this document was adapted after inspecting the
live file it modifies — no snippets are copy-pastes from the v1 first
draft that would fight the live code.
