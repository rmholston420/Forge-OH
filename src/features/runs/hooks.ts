'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchRuns, createRun, fetchAgentPresets } from './api';
import type { CreateRunRequest } from './schemas';
import { QUERY_KEYS } from '@/lib/query/query-keys';

export function useRuns() {
  return useQuery({
    queryKey: QUERY_KEYS.runs.list(),
    queryFn: fetchRuns,
    refetchInterval: 5000,
    staleTime: 4000,
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CreateRunRequest) => createRun(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.list() });
    },
  });
}

export function useAgentPresets() {
  return useQuery({
    queryKey: QUERY_KEYS.runs.presets(),
    queryFn: fetchAgentPresets,
    staleTime: 1000 * 60 * 5,
  });
}
