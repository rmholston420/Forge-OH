import type { RunSummary } from '@/lib/schemas/run';
import type { ToolEvent } from '@/lib/schemas/event';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRun(runId: string): Promise<RunSummary> {
  const res = await fetch(`${BFF}/api/runs/${runId}`);
  if (!res.ok) throw new Error(`Run not found: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchRunEvents(runId: string): Promise<ToolEvent[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/events`);
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  const json = await res.json();
  return json.data;
}
