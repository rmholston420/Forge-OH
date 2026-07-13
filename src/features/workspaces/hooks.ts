'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchWorkspaces } from './api';
import { QUERY_KEYS } from '@/lib/query/query-keys';

export function useWorkspaces() {
  return useQuery({
    queryKey: QUERY_KEYS.workspaces.list(),
    queryFn: fetchWorkspaces,
    staleTime: 1000 * 30,
  });
}
