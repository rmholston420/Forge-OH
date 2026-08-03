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
    OLLAMA_URL,
    PRIMARY_MODEL,
    VLLM_URL,
    ModelUnavailableError,
    ollama_health_check,
    route_request,
    vllm_health_check,
)

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


class ModelRoutingStatus(BaseModel):
    ollamaUrl: str
    vllmUrl: str
    primaryModel: str
    fastModel: str
    ollamaPrimaryHealthy: bool
    ollamaFastHealthy: bool
    vllmHealthy: bool
    probes: list[RoutingProbe]


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
    probes: list[RoutingProbe] = []
    scenarios = [
        ("agentic", 8000),
        ("simple", 8000),
        ("simple", 50000),
    ]

    for task_complexity, context_length in scenarios:
        try:
            selected = await route_request(task_complexity, context_length)
            probes.append(
                RoutingProbe(
                    taskComplexity=task_complexity,
                    contextLength=context_length,
                    selected=selected,
                )
            )
        except ModelUnavailableError as exc:
            probes.append(
                RoutingProbe(
                    taskComplexity=task_complexity,
                    contextLength=context_length,
                    error=str(exc),
                )
            )

    return ModelRoutingStatus(
        ollamaUrl=OLLAMA_URL,
        vllmUrl=VLLM_URL,
        primaryModel=PRIMARY_MODEL,
        fastModel=FAST_MODEL,
        ollamaPrimaryHealthy=await ollama_health_check(PRIMARY_MODEL),
        ollamaFastHealthy=await ollama_health_check(FAST_MODEL),
        vllmHealthy=await vllm_health_check(),
        probes=probes,
    )
