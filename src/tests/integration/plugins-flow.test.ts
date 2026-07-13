/**
 * plugins-flow.test.ts
 *
 * Integration test: full plugin registration → list → ping → delete lifecycle
 * using MSW to simulate the BFF /api/plugins endpoints.
 *
 * Tests the React Query cache invalidation contract:
 *   - after registerPlugin mutates, the plugin list query refetches
 *   - after deletePlugin mutates, the plugin disappears from the cache
 *   - after pingPlugin mutates, the result is stored in mutation state
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import React from 'react';
import { usePlugins, useRegisterPlugin, usePingPlugin, useDeletePlugin } from '@/lib/plugins/hooks';

const PLUGIN_A = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Auth Plugin',
  version: '1.0.0',
  baseUrl: 'https://auth-plugin.example.com',
  authType: 'none',
  capabilities: [],
};

const PLUGIN_B = {
  id: '00000000-0000-0000-0000-000000000002',
  name: 'Notify Plugin',
  version: '2.0.0',
  baseUrl: 'https://notify.example.com',
  authType: 'bearer',
  capabilities: ['run:started'],
};

// Server-side state
let serverPlugins = [PLUGIN_A];

const server = setupServer(
  http.get('/api/plugins', () => HttpResponse.json(serverPlugins)),

  http.post('/api/plugins', async ({ request }) => {
    const body = await request.json() as typeof PLUGIN_B;
    const created = { ...body, id: PLUGIN_B.id };
    serverPlugins = [...serverPlugins, created];
    return HttpResponse.json(created, { status: 201 });
  }),

  http.delete('/api/plugins/:id', ({ params }) => {
    serverPlugins = serverPlugins.filter((p) => p.id !== params.id);
    return new HttpResponse(null, { status: 204 });
  }),

  http.post('/api/plugins/:id/ping', ({ params }) => {
    const found = serverPlugins.find((p) => p.id === params.id);
    if (!found) return HttpResponse.json({ error: 'not found' }, { status: 404 });
    return HttpResponse.json({ ok: true, latencyMs: 15 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  serverPlugins = [PLUGIN_A]; // reset server state
});
afterAll(() => server.close());

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function W({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe('Plugin lifecycle', () => {
  it('initially lists only PLUGIN_A', async () => {
    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data![0].id).toBe(PLUGIN_A.id);
  });

  it('register then list shows both plugins', async () => {
    const wrapper = makeWrapper();
    const { result: listResult } = renderHook(() => usePlugins(), { wrapper });
    const { result: regResult } = renderHook(() => useRegisterPlugin(), { wrapper });

    await waitFor(() => expect(listResult.current.isSuccess).toBe(true));
    expect(listResult.current.data).toHaveLength(1);

    await act(async () => {
      regResult.current.mutate({
        name: PLUGIN_B.name,
        version: PLUGIN_B.version,
        baseUrl: PLUGIN_B.baseUrl,
        authType: 'bearer',
        capabilities: ['run:started'],
      });
    });
    await waitFor(() => expect(regResult.current.isSuccess).toBe(true));

    // Cache should be invalidated; re-fetched list should have both plugins
    await waitFor(() => expect(listResult.current.data).toHaveLength(2));
    expect(listResult.current.data!.find((p) => p.id === PLUGIN_B.id)).toBeDefined();
  });

  it('delete removes the plugin from the list', async () => {
    // Seed both plugins
    serverPlugins = [PLUGIN_A, PLUGIN_B];

    const wrapper = makeWrapper();
    const { result: listResult } = renderHook(() => usePlugins(), { wrapper });
    const { result: delResult } = renderHook(() => useDeletePlugin(), { wrapper });

    await waitFor(() => expect(listResult.current.isSuccess).toBe(true));
    expect(listResult.current.data).toHaveLength(2);

    await act(async () => { delResult.current.mutate(PLUGIN_B.id); });
    await waitFor(() => expect(delResult.current.isSuccess).toBe(true));

    await waitFor(() => expect(listResult.current.data).toHaveLength(1));
    expect(listResult.current.data!.find((p) => p.id === PLUGIN_B.id)).toBeUndefined();
  });

  it('ping returns latency and ok:true for a registered plugin', async () => {
    const wrapper = makeWrapper();
    const { result } = renderHook(() => usePingPlugin(), { wrapper });

    await act(async () => { result.current.mutate(PLUGIN_A.id); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({ ok: true, latencyMs: 15 });
  });

  it('ping returns error for an unknown plugin id', async () => {
    const wrapper = makeWrapper();
    const { result } = renderHook(() => usePingPlugin(), { wrapper });

    await act(async () => { result.current.mutate('00000000-0000-0000-0000-000000000099'); });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
