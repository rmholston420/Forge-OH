import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsKeys } from '@/lib/query/query-keys';
import { fetchSettings, updateSettings, resetSettings, fetchModelRoutingStatus } from './api';
import type { UpdateSettingsRequest } from '@/lib/schemas/settings';

export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: fetchSettings,
    staleTime: Infinity, // user-driven, no background poll
  });
}

export function useModelRoutingStatus() {
  return useQuery({
    queryKey: [...settingsKeys.all, 'model-routing'],
    queryFn: fetchModelRoutingStatus,
    refetchInterval: 15000,
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: UpdateSettingsRequest) => updateSettings(patch),
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: settingsKeys.all });
      const prev = qc.getQueryData(settingsKeys.all);
      qc.setQueryData(settingsKeys.all, (old: any) => ({ ...old, ...patch }));
      return { prev };
    },
    onError: (_err, _patch, ctx) => {
      if (ctx?.prev) qc.setQueryData(settingsKeys.all, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  });
}

export function useResetSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: resetSettings,
    onSuccess: () => qc.invalidateQueries({ queryKey: settingsKeys.all }),
  });
}
