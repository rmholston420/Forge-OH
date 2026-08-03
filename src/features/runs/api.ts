/**
 * src/features/runs/api.ts
 *
 * All BFF calls for the Runs feature.
 * Uses the canonical bffGet/bffPost from lib/api/client — never raw fetch.
 */
import type { RunSummary } from '@/lib/schemas/run';
import type { AgentPreset, CreateRunRequest } from './schemas';
import { bffGet, bffPost } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { unwrap } from '@/lib/api/response';

export async function fetchRuns(): Promise<RunSummary[]> {
  const result = await bffGet<{ data: RunSummary[] }>(ENDPOINTS.RUNS.list());
  return unwrap(result).data;
}

export async function createRun(req: CreateRunRequest): Promise<RunSummary> {
  const result = await bffPost<{ data: RunSummary }>(ENDPOINTS.RUNS.create(), req);
  return unwrap(result).data;
}

export async function fetchAgentPresets(): Promise<AgentPreset[]> {
  const result = await bffGet<{ data: AgentPreset[] }>(ENDPOINTS.AGENTS.listPresets());
  return unwrap(result).data;
}

// ---------------------------------------------------------------------------
// Stage 5 — lifecycle actions. All return the raw BFF ack; the caller triggers
// a run refetch so the RunSummary.status transitions land in the UI.
// ---------------------------------------------------------------------------

export type LifecycleAck = {
  ok: boolean;
  run_id: string;
  status: string;
  agent_server?: unknown;
};

export async function pauseRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.pause(runId), {});
  return unwrap(result);
}

export async function resumeRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.resume(runId), {});
  return unwrap(result);
}

export async function stopRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.stop(runId), {});
  return unwrap(result);
}

export async function approveRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.approve(runId), {});
  return unwrap(result);
}

export async function rejectRun(runId: string, reason?: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(
    ENDPOINTS.RUNS.reject(runId),
    reason ? { reason } : {},
  );
  return unwrap(result);
}
