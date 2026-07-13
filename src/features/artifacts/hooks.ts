'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRunArtifacts } from './api';

export function useRunArtifacts(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'artifacts'],
    queryFn: () => fetchRunArtifacts(runId),
    enabled: !!runId,
    refetchInterval: 5000,
  });
}
