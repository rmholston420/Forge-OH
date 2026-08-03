'use client';

/**
 * src/features/repograph/hooks.ts
 *
 * TanStack Query hooks for RepoGraph (Slice D.5).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_KEYS } from '@/lib/query/query-keys';
import {
  fetchCallers,
  fetchCallees,
  fetchCoChanged,
  fetchContextBundle,
  fetchRepoGraphHealth,
  indexWorkspace,
  searchSymbols,
  type ContextBundleArgs,
  type IndexArgs,
} from './api';

const STALE_MS = 30_000;

export function useRepoGraphHealth() {
  return useQuery({
    queryKey: QUERY_KEYS.repograph.health(),
    queryFn: fetchRepoGraphHealth,
    staleTime: STALE_MS,
  });
}

export function useIndexWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: IndexArgs) => indexWorkspace(args),
    onSuccess: () => {
      // A fresh index invalidates everything cached under 'repograph'.
      qc.invalidateQueries({ queryKey: QUERY_KEYS.repograph.all });
    },
  });
}

export function useSymbolSearch(
  repoKey: string | undefined,
  q: string,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.repograph.search(repoKey ?? '', q),
    queryFn: () => searchSymbols(repoKey!, q),
    enabled: enabled && Boolean(repoKey) && q.trim().length > 0,
    staleTime: STALE_MS,
  });
}

export function useCallers(
  repoKey: string | undefined,
  name: string | undefined,
  relPath?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.repograph.callers(repoKey ?? '', name ?? '', relPath),
    queryFn: () => fetchCallers(repoKey!, name!, relPath),
    enabled: enabled && Boolean(repoKey) && Boolean(name),
    staleTime: STALE_MS,
  });
}

export function useCallees(
  repoKey: string | undefined,
  relPath: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.repograph.callees(repoKey ?? '', relPath ?? ''),
    queryFn: () => fetchCallees(repoKey!, relPath!),
    enabled: enabled && Boolean(repoKey) && Boolean(relPath),
    staleTime: STALE_MS,
  });
}

export function useCoChanged(
  repoKey: string | undefined,
  relPath: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.repograph.coChanged(repoKey ?? '', relPath ?? ''),
    queryFn: () => fetchCoChanged(repoKey!, relPath!),
    enabled: enabled && Boolean(repoKey) && Boolean(relPath),
    staleTime: STALE_MS,
  });
}

export function useContextBundle(
  args: ContextBundleArgs | undefined,
  enabled = true,
) {
  const repoKey = args?.repoKey ?? '';
  const seeds = args?.seeds ?? [];
  return useQuery({
    queryKey: QUERY_KEYS.repograph.contextBundle(repoKey, seeds),
    queryFn: () => fetchContextBundle(args!),
    enabled: enabled && Boolean(args) && Boolean(repoKey) && seeds.length > 0,
    staleTime: STALE_MS,
  });
}
