'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchPlugins, installPlugin, togglePlugin, uninstallPlugin, pingPlugin } from './api';

export function usePlugins() {
  return useQuery({ queryKey: ['plugins'], queryFn: fetchPlugins });
}

export function useInstallPlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: installPlugin,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
  });
}

export function useTogglePlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => togglePlugin(id, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
  });
}

export function useUninstallPlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uninstallPlugin,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plugins'] }),
  });
}

export function usePingPlugin() {
  return useMutation({ mutationFn: pingPlugin });
}
