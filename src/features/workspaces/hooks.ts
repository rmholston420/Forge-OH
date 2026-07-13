import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { Workspace } from './schemas';

const BASE = '/api/workspaces';

export const workspaceKeys = {
  all:    ['workspaces']           as const,
  detail: (id: string) => ['workspaces', id] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useWorkspaces() {
  return useQuery<Workspace[]>({
    queryKey: workspaceKeys.all,
    queryFn:  () => fetch(BASE).then(r => r.json()),
    // Avoid treating every poll result as stale; 4 s matches the run-list hook.
    staleTime: 4_000,
  });
}

export function useWorkspace(id: string) {
  return useQuery<Workspace>({
    queryKey: workspaceKeys.detail(id),
    queryFn:  () => fetch(`${BASE}/${id}`).then(r => r.json()),
    enabled:  !!id,
    staleTime: 10_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Workspace>) =>
      fetch(BASE, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.all }),
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: Partial<Workspace> & { id: string }) =>
      fetch(`${BASE}/${id}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(patch),
      }).then(r => r.json()),
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: workspaceKeys.all });
      qc.invalidateQueries({ queryKey: workspaceKeys.detail(id) });
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      fetch(`${BASE}/${id}`, { method: 'DELETE' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.all }),
  });
}

export function useResetWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      fetch(`${BASE}/${id}/reset`, { method: 'POST' }).then(r => r.json()),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: workspaceKeys.all });
      qc.invalidateQueries({ queryKey: workspaceKeys.detail(id) });
    },
  });
}

export function useTestWorkspaceConnection() {
  return useMutation({
    mutationFn: (id: string) =>
      fetch(`${BASE}/${id}/test`, { method: 'POST' }).then(r => r.json()),
  });
}

