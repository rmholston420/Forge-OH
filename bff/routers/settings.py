"""
bff/routers/settings.py

Settings router — UI preferences + model-routing probe endpoint.

Naming note: local handler functions are suffixed _handler to avoid
shadowing the `get_settings` name imported from bff.settings (Pydantic
Settings singleton). Previously the collision caused the GET /api/settings
endpoint to return the Pydantic Settings object instead of SettingsResponse.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from bff.services.model_router import (
    FAST_MODEL,
    LLM_CODER_MAX_TOKENS,
    LLM_CODER_MODEL,
    LLM_CODER_URL,
    LLM_PLANNER_MAX_TOKENS,
    LLM_PLANNER_MODEL,
    LLM_PLANNER_URL,
    LLM_PRIMARY_BACKEND,
    OLLAMA_URL,
    PRIMARY_MODEL,
    VLLM_FALLBACK_MODEL,
    VLLM_URL,
    ModelUnavailableError,
    _vllm_role_health,
    ollama_health_check,
    route_by_role,
    vllm_health_check,
)

# F.19.3: taskComplexity → role for the legacy F.18 probe scenarios.
# Mirrors bff/routers/runs.py::_TASK_COMPLEXITY_TO_ROLE; agentic is a
# planner-class task, simple is a coder-class task. Kept here (not
# imported from runs.py) to avoid a router → router import cycle.
_LEGACY_TASK_TO_ROLE: dict[str, str] = {
    "fast": "coder",
    "simple": "coder",
    "medium": "coder",
    "complex": "planner",
    "reasoning": "planner",
    "planning": "planner",
    "agentic": "planner",
}

router = APIRouter(prefix="/settings", tags=["settings"])


class KeyboardShortcuts(BaseModel):
    newRun: str = "Shift+R"
    commandPalette: str = "Ctrl+K"
    focusSearch: str = "Ctrl+/"
    pauseRun: str = "Shift+P"
    approveStep: str = "Shift+A"


class SettingsResponse(BaseModel):
    theme: Literal["system", "light", "dark"] = "system"
    accentColor: Literal["teal", "blue", "purple", "orange", "gold", "green"] = "teal"
    fontSize: Literal["sm", "md", "lg"] = "md"
    defaultModel: str = "gpt-4o"
    defaultAgentPreset: str = "default"
    maxConcurrentRuns: int = 3
    autoApprove: bool = False
    streamingEnabled: bool = True
    keyboardShortcuts: KeyboardShortcuts = KeyboardShortcuts()


class SettingsPatch(BaseModel):
    theme: Literal["system", "light", "dark"] | None = None
    accentColor: Literal["teal", "blue", "purple", "orange", "gold", "green"] | None = None
    fontSize: Literal["sm", "md", "lg"] | None = None
    defaultModel: str | None = None
    defaultAgentPreset: str | None = None
    maxConcurrentRuns: int | None = None
    autoApprove: bool | None = None
    streamingEnabled: bool | None = None
    keyboardShortcuts: KeyboardShortcuts | None = None


class RoutingProbe(BaseModel):
    taskComplexity: str
    contextLength: int
    selected: str | None = None
    error: str | None = None


class RoleProbe(BaseModel):
    """F.19.2c: per-role routing probe. Reports the resolved backend,
    model, base_url, and max_tokens the router would pick right now.
    ``error`` is populated when no path (vLLM, supervisor swap, or
    Ollama fallback) is available for that role."""

    role: str
    backend: str | None = None
    model: str | None = None
    baseUrl: str | None = None
    maxTokens: int | None = None
    selected: str | None = None  # legacy 'backend/model' tagged form
    error: str | None = None


class ModelRoutingStatus(BaseModel):
    ollamaUrl: str
    vllmUrl: str
    primaryBackend: str
    primaryModel: str
    fastModel: str
    vllmModel: str
    ollamaPrimaryHealthy: bool
    ollamaFastHealthy: bool
    vllmHealthy: bool
    probes: list[RoutingProbe]
    # F.19.2c: role-scoped fields (additive).
    coderUrl: str
    coderModel: str
    coderMaxTokens: int
    coderVllmHealthy: bool
    plannerUrl: str
    plannerModel: str
    plannerMaxTokens: int
    plannerVllmHealthy: bool
    roleProbes: list[RoleProbe]


_SETTINGS = SettingsResponse()


# NOTE: routes use "" (empty string) not "/" to avoid FastAPI registering
# /api/settings/ with a trailing slash, which causes 307 redirects for
# clients that request /api/settings (no slash).


@router.get("", response_model=SettingsResponse)
def get_settings_handler():
    return _SETTINGS


@router.patch("", response_model=SettingsResponse)
def update_settings_handler(patch: SettingsPatch):
    global _SETTINGS
    data = _SETTINGS.model_dump()
    for field, value in patch.model_dump(exclude_none=True).items():
        data[field] = value
    _SETTINGS = SettingsResponse(**data)
    return _SETTINGS


@router.post("/reset", response_model=SettingsResponse)
def reset_settings_handler():
    global _SETTINGS
    _SETTINGS = SettingsResponse()
    return _SETTINGS


@router.get("/model-routing", response_model=ModelRoutingStatus)
async def get_model_routing_handler():
    # --- Legacy task-complexity probes (F.18 shape, kept for FE compat) ---
    # F.19.3: rebuilt on top of route_by_role. Each scenario maps its
    # taskComplexity to a role via _LEGACY_TASK_TO_ROLE and probes it.
    probes: list[RoutingProbe] = []
    scenarios = [
        ("agentic", 8000),
        ("simple", 8000),
        ("simple", 50000),
    ]
    for task_complexity, context_length in scenarios:
        role = _LEGACY_TASK_TO_ROLE.get(task_complexity.lower(), "coder")
        try:
            route = await route_by_role(role, context_length=context_length)
            probes.append(
                RoutingProbe(
                    taskComplexity=task_complexity,
                    contextLength=context_length,
                    selected=route.tagged,
                )
            )
        except Exception as exc:  # F.19.3: catch any role-resolution failure
            probes.append(
                RoutingProbe(
                    taskComplexity=task_complexity,
                    contextLength=context_length,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    # --- F.19.2c: per-role probes ---
    role_probes: list[RoleProbe] = []
    for role in ("coder", "planner"):
        try:
            route = await route_by_role(role)
            role_probes.append(
                RoleProbe(
                    role=role,
                    backend=route.backend,
                    model=route.model,
                    baseUrl=route.base_url,
                    maxTokens=route.max_tokens,
                    selected=route.tagged,
                )
            )
        except Exception as exc:  # F.19.3: catch any role-resolution failure
            role_probes.append(
                RoleProbe(role=role, error=f"{type(exc).__name__}: {exc}")
            )

    return ModelRoutingStatus(
        ollamaUrl=OLLAMA_URL,
        vllmUrl=VLLM_URL,
        primaryBackend=LLM_PRIMARY_BACKEND,
        primaryModel=PRIMARY_MODEL,
        fastModel=FAST_MODEL,
        vllmModel=VLLM_FALLBACK_MODEL,
        ollamaPrimaryHealthy=await ollama_health_check(PRIMARY_MODEL),
        ollamaFastHealthy=await ollama_health_check(FAST_MODEL),
        vllmHealthy=await vllm_health_check(),
        probes=probes,
        coderUrl=LLM_CODER_URL,
        coderModel=LLM_CODER_MODEL,
        coderMaxTokens=LLM_CODER_MAX_TOKENS,
        coderVllmHealthy=await _vllm_role_health(LLM_CODER_URL),
        plannerUrl=LLM_PLANNER_URL,
        plannerModel=LLM_PLANNER_MODEL,
        plannerMaxTokens=LLM_PLANNER_MAX_TOKENS,
        plannerVllmHealthy=await _vllm_role_health(LLM_PLANNER_URL),
        roleProbes=role_probes,
    )
