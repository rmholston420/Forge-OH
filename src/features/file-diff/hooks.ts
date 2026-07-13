'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRunFiles, fetchFileDiff } from './api';

export function useRunFiles(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'files'],
    queryFn: () => fetchRunFiles(runId),
    enabled: !!runId,
  });
}

export function useFileDiff(runId: string, path: string | null) {
  return useQuery({
    queryKey: ['runs', runId, 'files', path],
    queryFn: () => fetchFileDiff(runId, path!),
    enabled: !!runId && !!path,
  });
}
