import type { RunSummary } from '@/lib/schemas/run';
import type { AgentPreset, CreateRunRequest } from './schemas';
import { bffFetch } from '@/lib/http/bff-client';

export async function fetchRuns(): Promise<RunSummary[]> {
  const res = await bffFetch('/api/runs');
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function createRun(req: CreateRunRequest): Promise<RunSummary> {
  const res = await bffFetch('/api/runs', {
    method: 'POST',
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to create run: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchAgentPresets(): Promise<AgentPreset[]> {
  const res = await bffFetch('/api/agent-presets');
  if (!res.ok) throw new Error(`Failed to fetch agent presets: ${res.status}`);
  return res.json();
}
