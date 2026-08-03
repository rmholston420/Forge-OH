'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRunMetrics, fetchTrace, fetchTraceSpans, fetchTracesForRun } from './api';

export function useRunMetrics(runId: string, isActive: boolean) {
  return useQuery({
    queryKey: ['metrics', runId],
    queryFn: () => fetchRunMetrics(runId),
    refetchInterval: isActive ? 5000 : false,
    enabled: !!runId,
  });
}

export function useTracesForRun(runId: string, enabled = true) {
  return useQuery({
    queryKey: ['observability', 'runs', runId, 'traces'],
    queryFn: () => fetchTracesForRun(runId),
    enabled: enabled && Boolean(runId),
    staleTime: 10_000,
  });
}

export function useTrace(traceId: string, enabled = true) {
  return useQuery({
    queryKey: ['observability', 'traces', traceId],
    queryFn: () => fetchTrace(traceId),
    enabled: enabled && Boolean(traceId),
    staleTime: 10_000,
  });
}

export function useTraceSpans(traceId: string, enabled = true) {
  return useQuery({
    queryKey: ['observability', 'traces', traceId, 'spans'],
    queryFn: () => fetchTraceSpans(traceId),
    enabled: enabled && Boolean(traceId),
    staleTime: 10_000,
  });
}
