/**
 * src/features/inference-backends/hooks.ts
 *
 * React Query hook for the inference-backend health inventory.
 * The 10s refetch cadence matches the Stage 2.2 DoD in
 * docs/reconciliation-plan-stage-2.md § 2.2.7 (Ollama flip visible
 * within one poll interval).
 */
'use client';
import { useQuery } from '@tanstack/react-query';
import { QUERY_KEYS } from '@/lib/query/query-keys';
import { fetchInferenceBackends } from './api';

export function useInferenceBackends() {
  return useQuery({
    queryKey: QUERY_KEYS.inferenceBackends.list(),
    queryFn: fetchInferenceBackends,
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}
