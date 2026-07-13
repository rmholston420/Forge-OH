import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';
import type { CreateAgentPresetRequest, UpdateAgentPresetRequest } from './schemas';

const KEY = ['agent-presets'] as const;
const presetKey = (id: string) => [...KEY, id] as const;

export const usePresets = () =>
  useQuery({ queryKey: KEY, queryFn: api.fetchPresets });

export const usePreset = (id: string) =>
  useQuery({ queryKey: presetKey(id), queryFn: () => api.fetchPreset(id), enabled: !!id });

export function useCreatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: CreateAgentPresetRequest) => api.createPreset(b),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useUpdatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateAgentPresetRequest }) =>
      api.updatePreset(id, body),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: KEY });
      qc.setQueryData(presetKey(p.id), p);
    },
  });
}

export function useDeletePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deletePreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDuplicatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.duplicatePreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useSetDefaultPreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.setDefaultPreset(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
