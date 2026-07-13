from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional

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

_SETTINGS = SettingsResponse()

@router.get("/", response_model=SettingsResponse)
def get_settings():
    return _SETTINGS

@router.patch("/", response_model=SettingsResponse)
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
