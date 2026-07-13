import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { Workspace } from './schemas';
import { bffFetch } from '@/lib/http/bff-client';

const BASE = '/api/workspaces';

export const workspaceKeys = {
  all: ['workspaces'] as const,
  detail: (id: string) => ['workspaces', id] as const,
};

async function readJsonOrThrow(res: Response) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Workspace API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

export function useWorkspaces() {
  return useQuery<Workspace[]>({
    queryKey: workspaceKeys.all,
    queryFn: async () => {
      const res = await bffFetch(BASE);
      return readJsonOrThrow(res);
    },
    staleTime: 4_000,
  });
}

export function useWorkspace(id: string) {
  return useQuery<Workspace>({
    queryKey: workspaceKeys.detail(id),
    queryFn: async () => {
      const res = await bffFetch(`${BASE}/${id}`);
      return readJsonOrThrow(res);
    },
    enabled: !!id,
    staleTime: 10_000,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: Partial<Workspace>) => {
      const res = await bffFetch(BASE, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      return readJsonOrThrow(res);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.all }),
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...patch }: Partial<Workspace> & { id: string }) => {
      const res = await bffFetch(`${BASE}/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      return readJsonOrThrow(res);
    },
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: workspaceKeys.all });
      qc.invalidateQueries({ queryKey: workspaceKeys.detail(id) });
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await bffFetch(`${BASE}/${id}`, { method: 'DELETE' });
      return readJsonOrThrow(res);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.all }),
  });
}

export function useResetWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await bffFetch(`${BASE}/${id}/reset`, { method: 'POST' });
      return readJsonOrThrow(res);
    },
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: workspaceKeys.all });
      qc.invalidateQueries({ queryKey: workspaceKeys.detail(id) });
    },
  });
}

export function useTestWorkspaceConnection() {
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await bffFetch(`${BASE}/${id}/test`, { method: 'POST' });
      return readJsonOrThrow(res);
    },
  });
}
