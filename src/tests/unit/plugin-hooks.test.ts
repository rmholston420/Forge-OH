import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
  usePlugins,
  useRegisterPlugin,
  usePingPlugin,
  useDeletePlugin,
} from '@/lib/plugins/hooks';

const BASE = 'http://localhost:3000';

const server = setupServer(
  http.get(`${BASE}/api/plugins`, () =>
    HttpResponse.json({
      data: [
        {
          id: 'plugin-1',
          name: 'Plugin One',
          version: '1.0.0',
          baseUrl: 'http://plugin-one.local',
          authType: 'none',
          capabilities: ['run.started'],
        },
      ],
    })
  ),

  http.post(`${BASE}/api/plugins`, async ({ request }) => {
    const payload = (await request.clone().json()) as {
      name: string;
      version: string;
      baseUrl: string;
      authType: string;
      capabilities: string[];
    };

    return HttpResponse.json({
      data: {
        id: 'plugin-created',
        ...payload,
      },
    });
  }),

  http.post(`${BASE}/api/plugins/:id/ping`, ({ params }) =>
    HttpResponse.json({
      ok: true,
      pluginId: params.id,
      latencyMs: 42,
    })
  ),

  http.delete(`${BASE}/api/plugins/:id`, ({ params }) =>
    HttpResponse.json({
      ok: true,
      pluginId: params.id,
    })
  )
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe('plugin hooks', () => {
  it('usePlugins fetches plugin list', async () => {
    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data).toHaveLength(1);
    expect(result.current.data?.data[0].id).toBe('plugin-1');
  });

  it('useRegisterPlugin POSTs to /api/plugins and returns the created plugin with id', async () => {
    const { result } = renderHook(() => useRegisterPlugin(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current).toBeTruthy());

    await result.current.mutateAsync({
      name: 'Plugin Two',
      version: '1.0.0',
      baseUrl: 'http://plugin-two.local',
      authType: 'none',
      capabilities: ['run.started'],
    } as any);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data?.id ?? result.current.data?.id).toBe('plugin-created');
  });

  it('usePingPlugin POSTs to /api/plugins/:id/ping', async () => {
    const { result } = renderHook(() => usePingPlugin(), { wrapper: makeWrapper() });

    await result.current.mutateAsync('plugin-1');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.ok).toBe(true);
  });

  it('useDeletePlugin is defined', async () => {
    const { result } = renderHook(() => useDeletePlugin(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current).toBeTruthy());
  });

  it('usePlugins handles network error', async () => {
    server.use(
      http.get(`${BASE}/api/plugins`, () => HttpResponse.error())
    );

    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('useRegisterPlugin surfaces server 500', async () => {
    server.use(
      http.post(`${BASE}/api/plugins`, () =>
        HttpResponse.json({ error: 'boom' }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useRegisterPlugin(), { wrapper: makeWrapper() });

    await expect(
      result.current.mutateAsync({
        name: 'Broken',
        version: '1.0.0',
        baseUrl: 'http://broken.local',
        authType: 'none',
        capabilities: [],
      } as any)
    ).rejects.toBeTruthy();
  });
});
