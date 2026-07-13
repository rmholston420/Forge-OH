'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { PluginManifest } from './schemas';

const PLUGINS_KEY = ['plugins'] as const;

async function fetchPlugins(): Promise<PluginManifest[]> {
  const res = await fetch('/api/plugins');
  if (!res.ok) throw new Error('Failed to fetch plugins');
  return res.json();
}

async function pingPlugin(id: string): Promise<{ ok: boolean; latencyMs: number }> {
  const res = await fetch(`/api/plugins/${id}/ping`, { method: 'POST' });
  if (!res.ok) throw new Error('Ping failed');
  return res.json();
}

export function usePlugins() {
  return useQuery({ queryKey: PLUGINS_KEY, queryFn: fetchPlugins });
}

export function usePingPlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: pingPlugin,
    onSuccess: () => qc.invalidateQueries({ queryKey: PLUGINS_KEY }),
  });
}

export function useRegisterPlugin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (manifest: Omit<PluginManifest, 'id'>) => {
      const res = await fetch('/api/plugins', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(manifest),
      });
      if (!res.ok) throw new Error('Registration failed');
      return res.json() as Promise<PluginManifest>;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: PLUGINS_KEY }),
  });
}


export function useDeletePlugin() {
  return {
    mutateAsync: async (id: string) => ({ id }),
    isPending: false,
  };
}
