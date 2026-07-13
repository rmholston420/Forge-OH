import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';
import type { RegisterMcpServerRequest } from './schemas';

const MCP_KEY = ['mcp'] as const;
const mcpKey = (id: string) => ['mcp', id] as const;

export function useMcpServers() {
  return useQuery({ queryKey: MCP_KEY, queryFn: api.fetchMcpServers,
    refetchInterval: 15_000 });
}

export function useRegisterMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterMcpServerRequest) => api.registerMcpServer(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: MCP_KEY }),
  });
}

export function useDeleteMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteMcpServer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: MCP_KEY }),
  });
}

export function usePingMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.pingMcpServer(id),
    onSuccess: (result, id) => {
      qc.setQueryData(MCP_KEY, (old: any[]) =>
        old?.map(s => s.id === id ? { ...s, lastPingMs: result.latencyMs,
          status: result.ok ? 'connected' : 'error' } : s)
      );
    },
  });
}

export function useToggleMcpServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.toggleMcpServer(id),
    onSuccess: (server) => {
      qc.setQueryData(MCP_KEY, (old: any[]) =>
        old?.map(s => s.id === server.id ? server : s)
      );
    },
  });
}
