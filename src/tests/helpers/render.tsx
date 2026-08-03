/**
 * src/tests/helpers/render.tsx
 *
 * Custom render wrapper for @testing-library/react that provides a
 * QueryClientProvider so components which internally call useQueryClient,
 * useQuery, or useMutation don't throw "No QueryClient set".
 *
 * Usage:
 *   import { render, screen } from '@/tests/helpers/render';
 *   render(<MyComponent />);
 *
 * Re-exports everything from @testing-library/react so drop-in swap works.
 */
import * as React from 'react';
import { render as rtlRender, type RenderOptions, type RenderResult } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
}

export function render(
  ui: React.ReactElement,
  { queryClient, ...options }: CustomRenderOptions = {},
): RenderResult & { queryClient: QueryClient } {
  const qc = queryClient ?? makeQueryClient();
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
  const result = rtlRender(ui, { wrapper, ...options });
  return Object.assign(result, { queryClient: qc });
}

// Re-export everything else from @testing-library/react so tests can do:
//   import { render, screen, fireEvent } from '@/tests/helpers/render';
export * from '@testing-library/react';
