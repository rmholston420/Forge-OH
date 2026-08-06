import { RunSummarySchema, type RunSummary } from '@/lib/schemas/run';
import type { ToolEvent } from '@/lib/schemas/event';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

// Post-Stage-3 hygiene unification (2026-08-05): the BFF _STATUS_MAP at
// bff/routers/runs.py:101 and the RunStatusSchema at src/lib/schemas/run.ts
// now share the canonical underscore form (`awaiting_approval`), so the
// legacy boundary normalizer has been removed. `RunSummarySchema.parse`
// below is the tripwire that will fail loudly on any future drift.

export async function fetchRun(runId: string): Promise<RunSummary> {
  const res = await fetch(`${BFF}/api/runs/${runId}`);
  if (!res.ok) throw new Error(`Run not found: ${res.status}`);
  const json = await res.json();
  // Validate at the boundary. Zod default strips unknown keys (like the
  // BFF's `executionStatus`), so this only asserts on shape + enum drift.
  return RunSummarySchema.parse(json.data);
}

export async function fetchRunEvents(runId: string): Promise<ToolEvent[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/events`);
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  const json = await res.json();
  return json.data;
}
