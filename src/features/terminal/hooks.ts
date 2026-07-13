'use client';
import { useQuery } from '@tanstack/react-query';
import { fetchRunCommands } from './api';

export function useRunCommands(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'commands'],
    queryFn: () => fetchRunCommands(runId),
    enabled: !!runId,
    refetchInterval: 3000, // poll while run active
  });
}
