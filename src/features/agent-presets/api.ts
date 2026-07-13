import type { AgentPreset, CreateAgentPresetRequest, UpdateAgentPresetRequest } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export const fetchPresets = async (): Promise<AgentPreset[]> => {
  const r = await fetch(`${BASE}/agent-presets`);
  if (!r.ok) throw new Error('Failed to fetch presets');
  return r.json();
};

export const fetchPreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/agent-presets/${id}`);
  if (!r.ok) throw new Error('Preset not found');
  return r.json();
};

export const createPreset = async (body: CreateAgentPresetRequest): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/agent-presets`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('Failed to create preset');
  return r.json();
};

export const updatePreset = async (id: string, body: UpdateAgentPresetRequest): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/agent-presets/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('Failed to update preset');
  return r.json();
};

export const deletePreset = async (id: string): Promise<void> => {
  const r = await fetch(`${BASE}/agent-presets/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error('Failed to delete preset');
};

export const duplicatePreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/agent-presets/${id}/duplicate`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to duplicate preset');
  return r.json();
};

export const setDefaultPreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/agent-presets/${id}/set-default`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to set default');
  return r.json();
};
