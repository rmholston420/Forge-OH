'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchTrace } from './api';

export function useTrace(runId: string) {
  return useQuery({
    queryKey: ['trace', runId],
    queryFn: () => fetchTrace(runId),
    enabled: !!runId,
    staleTime: 30_000,
  });
}
