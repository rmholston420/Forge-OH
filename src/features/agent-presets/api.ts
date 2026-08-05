import type { AgentPreset, CreateAgentPresetRequest, UpdateAgentPresetRequest } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export const fetchPresets = async (): Promise<AgentPreset[]> => {
  const r = await fetch(`${BASE}/api/agent-presets`);
  if (!r.ok) throw new Error('Failed to fetch presets');
  // BFF returns {data: [...]} envelope (see bff/routers/agent_presets.py::list_presets).
  // Unwrap here so consumers always receive AgentPreset[].
  const body = await r.json().catch(() => null);
  if (Array.isArray(body)) return body;
  if (body && Array.isArray(body.data)) return body.data;
  return [];
};

export const fetchPreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/api/agent-presets/${id}`);
  if (!r.ok) throw new Error('Preset not found');
  return r.json();
};

export const createPreset = async (body: CreateAgentPresetRequest): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/api/agent-presets`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('Failed to create preset');
  return r.json();
};

export const updatePreset = async (id: string, body: UpdateAgentPresetRequest): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/api/agent-presets/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error('Failed to update preset');
  return r.json();
};

export const deletePreset = async (id: string): Promise<void> => {
  const r = await fetch(`${BASE}/api/agent-presets/${id}`, { method: 'DELETE' });
  if (!r.ok) throw new Error('Failed to delete preset');
};

export const duplicatePreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/api/agent-presets/${id}/duplicate`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to duplicate preset');
  return r.json();
};

export const setDefaultPreset = async (id: string): Promise<AgentPreset> => {
  const r = await fetch(`${BASE}/api/agent-presets/${id}/set-default`, { method: 'POST' });
  if (!r.ok) throw new Error('Failed to set default');
  return r.json();
};
