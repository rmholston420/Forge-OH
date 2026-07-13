'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRunMetrics } from './api';

export function useRunMetrics(runId: string, isActive: boolean) {
  return useQuery({
    queryKey: ['metrics', runId],
    queryFn: () => fetchRunMetrics(runId),
    refetchInterval: isActive ? 5000 : false,
    enabled: !!runId,
  });
}
