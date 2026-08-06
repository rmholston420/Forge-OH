from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agent-presets", tags=["agent-presets"])

# Stage 2.1.7 (amended plan): ``model`` is a free-form identifier the
# selected backend understands (e.g. ``qwen3-coder:32k`` for Ollama,
# ``qwen3.6-27b-int4-autoround`` for the coder vLLM). The old cloud
# ``Literal["gpt-4o", ...]`` was inaccurate on Colossus (no cloud
# routing exists in this codebase) and blocked local presets from
# being seeded. See KNOWN_ISSUES 2026-08-05.
ModelId = str

# Canonical backend ids — kept in sync with
# ``bff/services/inference_backends/registry.py``. Duplicated as a
# Literal here (not imported) so this router has no dependency on
# the backend registry module at import time; the registry is a
# runtime concern.
BackendId = Literal[
    "ollama",
    "vllm-coder",
    "vllm-planner",
    "vllm-legacy",
    "llamacpp",
    "sglang",
]

# Role hint for a preset. ``None`` = let ``route_by_role``'s
# taskComplexity mapping decide (backwards-compatible default).
RoleHint = Literal["coder", "planner"]


class LoopGuardConfig(BaseModel):
    enabled: bool = True
    windowSize: int = 20
    threshold: int = 3


class AgentPreset(BaseModel):
    id: str
    name: str
    description: str | None = None
    systemPrompt: str = ""
    model: ModelId = ""
    # Stage 2.1.7: optional backend pin. When set, the run-creation
    # path forwards this to ``route_by_role(backend_id=...)``.
    backendId: BackendId | None = None
    # Stage 2.1.7: optional explicit role. When set, wins over
    # taskComplexity mapping.
    role: RoleHint | None = None
    maxSteps: int = 100
    maxCost: float = 5.0
    temperature: float = 0.2
    topP: float = 0.95
    toolAllowlist: list[str] = []
    loopGuard: LoopGuardConfig = Field(default_factory=LoopGuardConfig)
    isDefault: bool = False
    createdAt: str
    updatedAt: str


class CreateRequest(BaseModel):
    name: str
    description: str | None = None
    systemPrompt: str = ""
    model: ModelId = ""
    backendId: BackendId | None = None
    role: RoleHint | None = None
    maxSteps: int = 100
    maxCost: float = 5.0
    temperature: float = 0.2
    topP: float = 0.95
    toolAllowlist: list[str] = []
    loopGuard: LoopGuardConfig = Field(default_factory=LoopGuardConfig)


class UpdateRequest(BaseModel):
    """All fields optional — only provided fields are merged."""

    name: str | None = None
    description: str | None = None
    systemPrompt: str | None = None
    model: ModelId | None = None
    backendId: BackendId | None = None
    role: RoleHint | None = None
    maxSteps: int | None = None
    maxCost: float | None = None
    temperature: float | None = None
    topP: float | None = None
    toolAllowlist: list[str] | None = None
    loopGuard: LoopGuardConfig | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


# Stage 2.1.7 (amended plan): seed with Colossus-local presets keyed
# to the canonical vLLM coder/planner topology (ADR-009 §3a) plus an
# Ollama fallback. Cloud presets are gone — this codebase never
# routed to them and having them as defaults blocked local runs.
_PRESETS: dict[str, AgentPreset] = {
    "ap-1": AgentPreset(
        id="ap-1",
        name="Coder — vLLM (c01 canonical)",
        description=(
            "Colossus coder role: Qwen3.6-27B INT4-AutoRound via vLLM at :8501. "
            "F.3 SWE-bench Verified: 26.6% raw pass@1. Default preset."
        ),
        systemPrompt="You are an expert software engineer. Think step by step.",
        model="qwen3.6-27b-int4-autoround",
        backendId="vllm-coder",
        role="coder",
        maxSteps=150,
        maxCost=0.0,
        isDefault=True,
        toolAllowlist=["filesystem", "bash", "browser"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(),
        updatedAt=_now(),
    ),
    "ap-2": AgentPreset(
        id="ap-2",
        name="Planner — vLLM (DSR1-Distill-32B AWQ)",
        description=(
            "Colossus planner role: DeepSeek-R1-Distill-32B AWQ via vLLM at :8511. "
            "Reasoning-heavy tasks and multi-step planning."
        ),
        systemPrompt="You are a planning assistant. Reason step by step before acting.",
        model="deepseek-r1-distill-32b-awq",
        backendId="vllm-planner",
        role="planner",
        maxSteps=80,
        maxCost=0.0,
        toolAllowlist=["filesystem", "bash", "browser", "search"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=15, threshold=2),
        createdAt=_now(),
        updatedAt=_now(),
    ),
    "ap-3": AgentPreset(
        id="ap-3",
        name="Coder — Ollama fallback",
        description=(
            "Coder role pinned to the Ollama runtime (qwen3-coder:32k). "
            "Use when the coder vLLM is offline or under supervision."
        ),
        systemPrompt="You are an expert software engineer. Think step by step.",
        model="qwen3-coder:32k",
        backendId="ollama",
        role="coder",
        maxSteps=150,
        maxCost=0.0,
        toolAllowlist=["filesystem", "bash", "browser"],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(),
        updatedAt=_now(),
    ),
}


# ---------------------------------------------------------------------------
# Read endpoints — no auth required
# ---------------------------------------------------------------------------


@router.get("")
def list_presets() -> dict:
    return {"data": [p.model_dump() for p in _PRESETS.values()]}


@router.get("/{preset_id}", response_model=AgentPreset)
def get_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p:
        raise HTTPException(404, "Preset not found")
    return p


# ---------------------------------------------------------------------------
# Write endpoints — require 'write' role
# ---------------------------------------------------------------------------


@router.post("", response_model=AgentPreset)
def create_preset(body: CreateRequest):
    p = AgentPreset(
        id=str(uuid4()), isDefault=False, createdAt=_now(), updatedAt=_now(), **body.model_dump()
    )
    _PRESETS[p.id] = p
    return p


@router.patch("/{preset_id}", response_model=AgentPreset)
def update_preset(preset_id: str, body: UpdateRequest):
    p = _PRESETS.get(preset_id)
    if not p:
        raise HTTPException(404, "Preset not found")
    updated = p.model_copy(update={**body.model_dump(exclude_none=True), "updatedAt": _now()})
    _PRESETS[preset_id] = updated
    return updated


@router.delete("/{preset_id}")
def delete_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p:
        raise HTTPException(404, "Preset not found")
    if p.isDefault:
        raise HTTPException(400, "Cannot delete the default preset")
    del _PRESETS[preset_id]
    return {"ok": True}


@router.post("/{preset_id}/duplicate", response_model=AgentPreset)
def duplicate_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p:
        raise HTTPException(404, "Preset not found")
    clone = p.model_copy(
        update={
            "id": str(uuid4()),
            "name": f"{p.name} (copy)",
            "isDefault": False,
            "createdAt": _now(),
            "updatedAt": _now(),
        }
    )
    _PRESETS[clone.id] = clone
    return clone


@router.post("/{preset_id}/set-default", response_model=AgentPreset)
def set_default(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p:
        raise HTTPException(404, "Preset not found")
    for pid, preset in _PRESETS.items():
        _PRESETS[pid] = preset.model_copy(
            update={"isDefault": pid == preset_id, "updatedAt": _now()}
        )
    return _PRESETS[preset_id]
