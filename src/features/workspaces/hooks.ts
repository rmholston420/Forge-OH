'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchWorkspaces, fetchWorkspace, createWorkspace,
  updateWorkspace, deleteWorkspace, testWorkspaceConnection,
} from './api';

export function useWorkspaces() {
  return useQuery({ queryKey: ['workspaces'], queryFn: fetchWorkspaces });
}

export function useWorkspace(id: string) {
  return useQuery({
    queryKey: ['workspaces', id],
    queryFn: () => fetchWorkspace(id),
    enabled: !!id,
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createWorkspace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspaces'] }),
  });
}

export function useUpdateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateWorkspace>[1] }) =>
      updateWorkspace(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspaces'] }),
  });
}

export function useDeleteWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteWorkspace,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspaces'] }),
  });
}

export function useTestWorkspaceConnection() {
  return useMutation({ mutationFn: testWorkspaceConnection });
}
