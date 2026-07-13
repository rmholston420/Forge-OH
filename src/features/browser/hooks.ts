'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchBrowserFrames } from './api';

export function useBrowserFrames(runId: string, isActive: boolean) {
  return useQuery({
    queryKey: ['browser', runId],
    queryFn: () => fetchBrowserFrames(runId),
    refetchInterval: isActive ? 2000 : false,
    enabled: !!runId,
  });
}
