import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query/query-keys';
import { fetchSecrets, createSecret, rotateSecret, deleteSecret } from './api';

export function useSecrets() {
  return useQuery({
    queryKey: queryKeys.secrets.list(),
    queryFn: fetchSecrets,
    // Secrets change rarely — poll less aggressively
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useCreateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSecret,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.secrets.list() }),
  });
}

export function useRotateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, newValue }: { id: string; newValue: string }) =>
      rotateSecret(id, newValue),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.secrets.list() }),
  });
}

export function useDeleteSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSecret(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.secrets.list() }),
  });
}
