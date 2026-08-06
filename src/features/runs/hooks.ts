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
  forkRun,
  sendRunMessage,
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

/**
 * Stage 6.4 — forkRun mutation.
 *
 * Variables shape:
 *   { runId: string, fromEventId?: string }
 *
 * Backward-compatibility: a bare ``string`` variable still works and
 * behaves as a full-fork (see the coercion in ``mutationFn``).  This keeps
 * older call sites like ``ForkRunModal`` compiling without change.
 */
export type ForkRunVars = { runId: string; fromEventId?: string } | string;

function _normalizeForkVars(vars: ForkRunVars): { runId: string; fromEventId?: string } {
  return typeof vars === 'string' ? { runId: vars } : vars;
}

export function useForkRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: ForkRunVars) => {
      const v = _normalizeForkVars(vars);
      return forkRun(v.runId, v.fromEventId ? { fromEventId: v.fromEventId } : undefined);
    },
    onSuccess: (data, vars) => {
      const { runId } = _normalizeForkVars(vars);
      invalidateRun(qc, runId);
      // The forked run is a fresh row in the list; ensure it is fetched.
      qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.list() });
      if (data?.forked_id) {
        qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.detail(data.forked_id) });
      }
    },
  });
}

// Stage 1.6 (reconciliation-plan-v1) — useSendRunMessage.
// Invalidates the events query so the new user message renders as soon as
// agent-server surfaces it back via GET /api/runs/{id}/events (bootstrap)
// or Socket.IO (live).
export function useSendRunMessage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { runId: string; message: string }) =>
      sendRunMessage(vars.runId, vars.message),
    onSuccess: (_data, vars) => {
      invalidateRun(qc, vars.runId);
      qc.invalidateQueries({ queryKey: QUERY_KEYS.runs.events(vars.runId) });
    },
  });
}
