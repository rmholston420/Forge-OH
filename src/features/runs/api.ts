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
