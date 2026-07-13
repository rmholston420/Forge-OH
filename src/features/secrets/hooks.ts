'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchSecrets, upsertSecret, deleteSecret, rotateSecret } from './api';

export function useSecrets() {
  return useQuery({ queryKey: ['secrets'], queryFn: fetchSecrets });
}

export function useUpsertSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertSecret,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['secrets'] }),
  });
}

export function useDeleteSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSecret,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['secrets'] }),
  });
}

export function useRotateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => rotateSecret(id, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['secrets'] }),
  });
}
