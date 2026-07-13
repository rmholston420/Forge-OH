import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';
import type { CreateSecretRequest } from './schemas';

const SECRETS_KEY = ['secrets'] as const;

export function useSecrets(scope?: string) {
  return useQuery({
    queryKey: scope ? [...SECRETS_KEY, scope] : SECRETS_KEY,
    queryFn: () => api.fetchSecrets(scope),
    refetchInterval: 30_000,
  });
}

export function useCreateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateSecretRequest) => api.createSecret(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SECRETS_KEY }),
  });
}

export function useRotateSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, newValue }: { id: string; newValue: string }) =>
      api.rotateSecret(id, newValue),
    onSuccess: () => qc.invalidateQueries({ queryKey: SECRETS_KEY }),
  });
}

export function useDeleteSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteSecret(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SECRETS_KEY }),
  });
}
