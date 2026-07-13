'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRun, fetchRunEvents } from './api';
import { QUERY_KEYS } from '@/lib/query/query-keys';

export function useRunDetail(runId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.runs.detail(runId),
    queryFn: () => fetchRun(runId),
    refetchInterval: 3000,
    enabled: !!runId,
  });
}

export function useRunEvents(runId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.runs.events(runId),
    queryFn: () => fetchRunEvents(runId),
    enabled: !!runId,
  });
}
