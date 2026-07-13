'use client';
import React, { useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { getQueryClient } from '@/lib/query/query-client';

export function Providers({ children }: { children: React.ReactNode }) {
  // Use useState initialiser to guarantee the QueryClient is created once per
  // component mount, not on every render. Without this guard, a parent
  // re-render would call getQueryClient() again and — on the server — produce
  // a fresh client, wiping the entire TanStack Query cache.
  const [queryClient] = useState(() => getQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
