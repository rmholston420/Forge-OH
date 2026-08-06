import { useQuery } from '@tanstack/react-query';
import { QUERY_KEYS } from '@/lib/query/query-keys';
import { fetchRecentWrites } from './api';

export function useRecentMemoryWrites(limit = 50) {
  return useQuery({
    queryKey: QUERY_KEYS.memory.recentWrites(limit),
    queryFn: () => fetchRecentWrites(limit),
    refetchInterval: 15_000,
    retry: (failureCount, err) => {
      // Don't hammer when BFF says the service is unavailable.
      if ((err as Error & { code?: string })?.code === 'MEMORY_UNAVAILABLE') return false;
      return failureCount < 2;
    },
  });
}
