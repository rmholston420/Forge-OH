from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timezone
import copy

router = APIRouter(prefix='/agent-presets', tags=['agent-presets'])

ModelId = Literal['gpt-4o', 'claude-opus-4', 'gemini-2.5-pro', 'local-llama']

class LoopGuardConfig(BaseModel):
    enabled:    bool  = True
    windowSize: int   = 20
    threshold:  int   = 3

class AgentPreset(BaseModel):
    id:            str
    name:          str
    description:   Optional[str]  = None
    systemPrompt:  str            = ''
    model:         ModelId        = 'gpt-4o'
    maxSteps:      int            = 100
    maxCost:       float          = 5.0
    temperature:   float          = 0.2
    topP:          float          = 0.95
    toolAllowlist: list[str]      = []
    loopGuard:     LoopGuardConfig = Field(default_factory=LoopGuardConfig)
    isDefault:     bool           = False
    createdAt:     str
    updatedAt:     str

class CreateRequest(BaseModel):
    name:          str
    description:   Optional[str]  = None
    systemPrompt:  str            = ''
    model:         ModelId        = 'gpt-4o'
    maxSteps:      int            = 100
    maxCost:       float          = 5.0
    temperature:   float          = 0.2
    topP:          float          = 0.95
    toolAllowlist: list[str]      = []
    loopGuard:     LoopGuardConfig = Field(default_factory=LoopGuardConfig)

def _now(): return datetime.now(timezone.utc).isoformat()

_PRESETS: dict[str, AgentPreset] = {
    'ap-1': AgentPreset(
        id='ap-1', name='General Dev',
        description='Balanced preset for software development tasks.',
        systemPrompt='You are an expert software engineer. Think step by step.',
        model='gpt-4o', maxSteps=150, maxCost=8.0, isDefault=True,
        toolAllowlist=['filesystem', 'bash', 'browser'],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=20, threshold=3),
        createdAt=_now(), updatedAt=_now(),
    ),
    'ap-2': AgentPreset(
        id='ap-2', name='Research Agent',
        description='Optimised for web research and document synthesis.',
        systemPrompt='You are a research assistant. Cite sources.',
        model='claude-opus-4', maxSteps=80, maxCost=12.0,
        toolAllowlist=['browser', 'search'],
        loopGuard=LoopGuardConfig(enabled=True, windowSize=15, threshold=2),
        createdAt=_now(), updatedAt=_now(),
    ),
}

@router.get('', response_model=list[AgentPreset])
def list_presets(): return list(_PRESETS.values())

@router.get('/{preset_id}', response_model=AgentPreset)
def get_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p: raise HTTPException(404, 'Preset not found')
    return p

@router.post('', response_model=AgentPreset)
def create_preset(body: CreateRequest):
    p = AgentPreset(id=str(uuid4()), isDefault=False,
                    createdAt=_now(), updatedAt=_now(), **body.dict())
    _PRESETS[p.id] = p
    return p

@router.patch('/{preset_id}', response_model=AgentPreset)
def update_preset(preset_id: str, body: dict):
    p = _PRESETS.get(preset_id)
    if not p: raise HTTPException(404, 'Preset not found')
    updated = p.copy(update={**body, 'updatedAt': _now()})
    _PRESETS[preset_id] = updated
    return updated

@router.delete('/{preset_id}')
def delete_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p: raise HTTPException(404, 'Preset not found')
    if p.isDefault: raise HTTPException(400, 'Cannot delete the default preset')
    del _PRESETS[preset_id]
    return {'ok': True}

@router.post('/{preset_id}/duplicate', response_model=AgentPreset)
def duplicate_preset(preset_id: str):
    p = _PRESETS.get(preset_id)
    if not p: raise HTTPException(404, 'Preset not found')
    clone = p.copy(update={'id': str(uuid4()), 'name': f'{p.name} (copy)',
                            'isDefault': False, 'createdAt': _now(), 'updatedAt': _now()})
    _PRESETS[clone.id] = clone
    return clone

@router.post('/{preset_id}/set-default', response_model=AgentPreset)
def set_default(preset_id: str):
    if preset_id not in _PRESETS: raise HTTPException(404, 'Preset not found')
    for pid, p in _PRESETS.items():
        _PRESETS[pid] = p.copy(update={'isDefault': pid == preset_id, 'updatedAt': _now()})
    return _PRESETS[preset_id]
