import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query/query-keys';
import {
  fetchWorkspaces,
  fetchWorkspace,
  resetWorkspace,
  duplicateWorkspace,
  deleteWorkspace,
} from './api';

export function useWorkspaces() {
  return useQuery({
    queryKey: queryKeys.workspaces.list(),
    queryFn: fetchWorkspaces,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useWorkspace(id: string | null) {
  return useQuery({
    queryKey: queryKeys.workspaces.detail(id ?? ''),
    queryFn: () => fetchWorkspace(id!),
    enabled: !!id,
    staleTime: 15_000,
  });
}

export function useResetWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => resetWorkspace(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.workspaces.list() });
    },
  });
}

export function useDuplicateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => duplicateWorkspace(id, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.workspaces.list() });
    },
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWorkspace(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.workspaces.list() });
    },
  });
}
