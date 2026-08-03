/**
 * src/features/run-detail/plan-hooks.ts
 *
 * TanStack Query hooks for the run plan tab.
 */
import { useQuery } from '@tanstack/react-query';
import { fetchRunPlan } from './plan-api';

export function useRunPlan(runId: string, enabled = true) {
  return useQuery({
    queryKey: ['run', runId, 'plan'],
    queryFn: () => fetchRunPlan(runId),
    enabled: enabled && Boolean(runId),
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}
