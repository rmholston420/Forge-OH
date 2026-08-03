'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchRuns,
  createRun,
  fetchAgentPresets,
  pauseRun,
  resumeRun,
  stopRun,
  approveRun,
  rejectRun,
} from './api';
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

// ---------------------------------------------------------------------------
// Stage 5 — run lifecycle mutations.
//
// All five invalidate BOTH the list and the individual run detail so the
// updated agent-server execution_status flows back into the UI on the next
// poll (RunSummary.status).
// ---------------------------------------------------------------------------

function invalidateRun(qc: ReturnType<typeof useQueryClient>, runId: string) {
  qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.list() });
  qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.detail(runId) });
}

export function usePauseRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => pauseRun(runId),
    onSuccess: (_data, runId) => invalidateRun(qc, runId),
  });
}

export function useResumeRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => resumeRun(runId),
    onSuccess: (_data, runId) => invalidateRun(qc, runId),
  });
}

export function useStopRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => stopRun(runId),
    onSuccess: (_data, runId) => invalidateRun(qc, runId),
  });
}

export function useApproveRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => approveRun(runId),
    onSuccess: (_data, runId) => invalidateRun(qc, runId),
  });
}

export function useRejectRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { runId: string; reason?: string }) =>
      rejectRun(vars.runId, vars.reason),
    onSuccess: (_data, vars) => invalidateRun(qc, vars.runId),
  });
}
