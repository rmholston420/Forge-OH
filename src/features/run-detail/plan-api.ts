/**
 * src/features/run-detail/plan-api.ts
 *
 * BFF calls for the run plan tab. Fetches PlanNode[] reconstructed from
 * task_tracker observations on the agent-server events.
 */
import { bffGet } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import type { PlanNode } from '@/lib/schemas/plan';

export async function fetchRunPlan(runId: string): Promise<PlanNode[]> {
  const result = await bffGet<{ data: PlanNode[] }>(ENDPOINTS.RUNS.plan(runId));
  return unwrap(result).data ?? [];
}
