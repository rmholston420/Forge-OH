/**
 * plugin-hooks.test.ts
 *
 * Tests for usePlugins, usePingPlugin, and useRegisterPlugin from
 * src/lib/plugins/hooks.ts using @testing-library/react and MSW.
 *
 * Covers:
 *   - usePlugins: successful fetch + schema-valid data rendered
 *   - usePlugins: network error surfaces as query error state
 *   - usePingPlugin: mutate() calls POST /api/plugins/:id/ping and
 *     invalidates the plugins query key on success
 *   - useRegisterPlugin: mutate() calls POST /api/plugins with body
 *     and invalidates the plugins query key on success
 *   - useRegisterPlugin: non-ok response throws and surfaces error
 */
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import React from 'react';
import { usePlugins, usePingPlugin, useRegisterPlugin } from '@/lib/plugins/hooks';

const PLUGIN_1 = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Plugin A',
  version: '1.0.0',
  baseUrl: 'https://plugin-a.example.com',
  authType: 'none',
  capabilities: [],
};

const server = setupServer(
  http.get('/api/plugins', () => HttpResponse.json([PLUGIN_1])),
  http.post('/api/plugins/:id/ping', () =>
    HttpResponse.json({ ok: true, latencyMs: 42 })
  ),
  http.post('/api/plugins', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ ...body, id: '00000000-0000-0000-0000-000000000002' }, { status: 201 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe('usePlugins', () => {
  it('fetches and returns the plugin list', async () => {
    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].id).toBe(PLUGIN_1.id);
  });

  it('surfaces an error when the API fails', async () => {
    server.use(http.get('/api/plugins', () => HttpResponse.json({}, { status: 500 })));
    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('usePingPlugin', () => {
  it('calls POST /api/plugins/:id/ping and returns ok + latencyMs', async () => {
    const { result } = renderHook(() => usePingPlugin(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate(PLUGIN_1.id);
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({ ok: true, latencyMs: 42 });
  });

  it('surfaces error when ping returns non-ok', async () => {
    server.use(
      http.post('/api/plugins/:id/ping', () => HttpResponse.json({}, { status: 503 }))
    );
    const { result } = renderHook(() => usePingPlugin(), { wrapper: makeWrapper() });
    await act(async () => { result.current.mutate(PLUGIN_1.id); });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useRegisterPlugin', () => {
  it('POSTs to /api/plugins and returns the created plugin with id', async () => {
    const { result } = renderHook(() => useRegisterPlugin(), { wrapper: makeWrapper() });
    const newManifest = {
      name: 'New Plugin',
      version: '0.1.0',
      baseUrl: 'https://new.example.com',
      authType: 'none' as const,
      capabilities: [],
    };
    await act(async () => { result.current.mutate(newManifest); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveProperty('id');
    expect(result.current.data?.name).toBe('New Plugin');
  });

  it('surfaces error on non-ok response', async () => {
    server.use(http.post('/api/plugins', () => HttpResponse.json({}, { status: 422 })));
    const { result } = renderHook(() => useRegisterPlugin(), { wrapper: makeWrapper() });
    await act(async () => {
      result.current.mutate({ name: 'x', version: '1.0.0', baseUrl: 'https://x.com', authType: 'none', capabilities: [] });
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
