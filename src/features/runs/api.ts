import type { RunSummary } from '@/lib/schemas/run';
import type { AgentPreset, CreateRunRequest } from './schemas';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${BFF}/api/runs`);
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function createRun(req: CreateRunRequest): Promise<RunSummary> {
  const res = await fetch(`${BFF}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Failed to create run: ${res.status}`);
  const json = await res.json();
  return json.data;
}

// NOTE: agent_presets router (prefix=/agent-presets) returns a bare list,
// not a {data:[]} envelope — so we do NOT unwrap .data here.
export async function fetchAgentPresets(): Promise<AgentPreset[]> {
  const res = await fetch(`${BFF}/api/agent-presets`);
  if (!res.ok) throw new Error(`Failed to fetch agent presets: ${res.status}`);
  return res.json();
}
