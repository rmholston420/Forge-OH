import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query/query-keys';
import {
  fetchMCPServers,
  toggleMCPServer,
  pingMCPServer,
  fetchPlugins,
  enablePlugin,
  disablePlugin,
  savePluginConfig,
} from './api';

export function useMCPServers() {
  return useQuery({
    queryKey: queryKeys.mcp.list(),
    queryFn: fetchMCPServers,
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}

export function useToggleMCPServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enable }: { id: string; enable: boolean }) =>
      toggleMCPServer(id, enable),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.mcp.list() }),
  });
}

export function usePingMCPServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pingMCPServer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.mcp.list() }),
  });
}

export function usePlugins() {
  return useQuery({
    queryKey: queryKeys.plugins.list(),
    queryFn: fetchPlugins,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useTogglePlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enable }: { id: string; enable: boolean }) =>
      enable ? enablePlugin(id) : disablePlugin(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plugins.list() }),
  });
}

export function useSavePluginConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, config }: { id: string; config: Record<string, unknown> }) =>
      savePluginConfig(id, config),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plugins.list() }),
  });
}
