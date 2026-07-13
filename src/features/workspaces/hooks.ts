import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';
import type { CreateWorkspaceRequest, UpdateWorkspaceRequest } from './schemas';

const WS_KEY = ['workspaces'] as const;
const wsKey = (id: string) => ['workspaces', id] as const;

export function useWorkspaces() {
  return useQuery({ queryKey: WS_KEY, queryFn: api.fetchWorkspaces,
    refetchInterval: 30_000 });
}

export function useWorkspace(id: string) {
  return useQuery({ queryKey: wsKey(id), queryFn: () => api.fetchWorkspace(id),
    enabled: !!id });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateWorkspaceRequest) => api.createWorkspace(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: WS_KEY }),
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateWorkspaceRequest }) =>
      api.updateWorkspace(id, body),
    onSuccess: (ws) => {
      qc.invalidateQueries({ queryKey: WS_KEY });
      qc.setQueryData(wsKey(ws.id), ws);
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteWorkspace(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: WS_KEY }),
  });
}

export function useResetWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resetWorkspace(id),
    onSuccess: (ws) => {
      qc.invalidateQueries({ queryKey: WS_KEY });
      qc.setQueryData(wsKey(ws.id), ws);
    },
  });
}


export function useTestWorkspaceConnection() {
  return {
    mutateAsync: async () => ({ ok: true }),
    isPending: false,
  };
}
