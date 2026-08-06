import type { RunSummary } from '@/lib/schemas/run';
import type { ToolEvent } from '@/lib/schemas/event';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

// Stage 3.2 — normalize BFF wire status (`awaiting_approval` underscore)
// into the schema's kebab-case (`awaiting-approval`). The BFF _STATUS_MAP
// at bff/routers/runs.py:97 and the RunStatusSchema at
// src/lib/schemas/run.ts:13 have drifted; unifying them is a separate
// hygiene commit. Until then, translate at the boundary so
// `run.status === 'awaiting-approval'` in page.tsx actually fires when
// ConfirmRisky pauses the agent.
function _normalizeRunStatus<T extends { status?: unknown } | null | undefined>(run: T): T {
  if (run && typeof (run as { status?: unknown }).status === 'string') {
    const s = (run as { status: string }).status;
    if (s === 'awaiting_approval') {
      return { ...(run as object), status: 'awaiting-approval' } as T;
    }
  }
  return run;
}

export async function fetchRun(runId: string): Promise<RunSummary> {
  const res = await fetch(`${BFF}/api/runs/${runId}`);
  if (!res.ok) throw new Error(`Run not found: ${res.status}`);
  const json = await res.json();
  return _normalizeRunStatus(json.data) as RunSummary;
}

export async function fetchRunEvents(runId: string): Promise<ToolEvent[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/events`);
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  const json = await res.json();
  return json.data;
}
