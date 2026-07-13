from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional

from bff.services.model_router import (
    OLLAMA_URL,
    VLLM_URL,
    PRIMARY_MODEL,
    FAST_MODEL,
    ollama_health_check,
    vllm_health_check,
    route_request,
    ModelUnavailableError,
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
    theme: Optional[Literal["system", "light", "dark"]] = None
    accentColor: Optional[Literal["teal", "blue", "purple", "orange", "gold", "green"]] = None
    fontSize: Optional[Literal["sm", "md", "lg"]] = None
    defaultModel: Optional[str] = None
    defaultAgentPreset: Optional[str] = None
    maxConcurrentRuns: Optional[int] = None
    autoApprove: Optional[bool] = None
    streamingEnabled: Optional[bool] = None
    keyboardShortcuts: Optional[KeyboardShortcuts] = None


class RoutingProbe(BaseModel):
    taskComplexity: str
    contextLength: int
    selected: Optional[str] = None
    error: Optional[str] = None


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
# /api/settings/ with a trailing slash, which would cause 307 redirects
# for clients that request /api/settings (no slash).

@router.get("", response_model=SettingsResponse)
def get_settings():
    return _SETTINGS


@router.patch("", response_model=SettingsResponse)
def update_settings(patch: SettingsPatch):
    global _SETTINGS
    data = _SETTINGS.model_dump()
    for field, value in patch.model_dump(exclude_none=True).items():
        data[field] = value
    _SETTINGS = SettingsResponse(**data)
    return _SETTINGS


@router.post("/reset", response_model=SettingsResponse)
def reset_settings():
    global _SETTINGS
    _SETTINGS = SettingsResponse()
    return _SETTINGS


@router.get("/model-routing", response_model=ModelRoutingStatus)
async def get_model_routing():
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
