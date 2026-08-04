/**
 * React-Query hooks over the ``/api/selfeval`` surface. Mirrors the shape
 * used in features/metrics/hooks.ts. ``useStatus`` polls every 5 seconds
 * while a cycle is in flight so the Run-now button re-enables cleanly.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from './api';

const CYCLE_STALE_MS = 30 * 1000; // 30s — cycles are cheap to re-list
const PROPOSAL_STALE_MS = 30 * 1000;

export const useCycles = () =>
  useQuery({
    queryKey: ['selfeval', 'cycles'],
    queryFn: () => api.fetchCycles(),
    staleTime: CYCLE_STALE_MS,
  });

export const useCycle = (filename: string | null) =>
  useQuery({
    queryKey: ['selfeval', 'cycle', filename],
    queryFn: () => api.fetchCycle(filename as string),
    enabled: Boolean(filename),
    staleTime: CYCLE_STALE_MS,
  });

export const useProposals = (date?: string) =>
  useQuery({
    queryKey: ['selfeval', 'proposals', date ?? null],
    queryFn: () => api.fetchProposals(date),
    staleTime: PROPOSAL_STALE_MS,
  });

export const useProposal = (filename: string | null) =>
  useQuery({
    queryKey: ['selfeval', 'proposal', filename],
    queryFn: () => api.fetchProposal(filename as string),
    enabled: Boolean(filename),
    staleTime: PROPOSAL_STALE_MS,
  });

export const useStatus = () =>
  useQuery({
    queryKey: ['selfeval', 'status'],
    queryFn: () => api.fetchStatus(),
    // Poll while a cycle is running. When not running, still poll every 30s so
    // a systemctl-triggered run initiated from a terminal shows up in the UI.
    refetchInterval: (query) => (query.state.data?.running ? 5_000 : 30_000),
  });

export const useRunNow = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.postRun(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['selfeval', 'status'] });
      qc.invalidateQueries({ queryKey: ['selfeval', 'cycles'] });
    },
  });
};
