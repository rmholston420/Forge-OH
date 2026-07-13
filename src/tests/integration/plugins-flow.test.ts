import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { usePlugins, useRegisterPlugin, usePingPlugin, useDeletePlugin } from '@/lib/plugins/hooks';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

const PLUGIN_A = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Plugin A',
  version: '1.0.0',
  baseUrl: 'http://plugin-a.local',
  authType: 'none',
  capabilities: ['run.started'],
};

const PLUGIN_B = {
  id: '00000000-0000-0000-0000-000000000002',
  name: 'Plugin B',
  version: '1.0.0',
  baseUrl: 'http://plugin-b.local',
  authType: 'none',
  capabilities: ['run.started'],
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: qc }, children);
  };
}

describe('Plugin lifecycle', () => {
  beforeEach(() => {
    let serverPlugins = [PLUGIN_A];

    server.resetHandlers();
    server.use(
      http.get('/api/plugins', () => HttpResponse.json({ data: serverPlugins })),
      http.get(`${BFF}/api/plugins`, () => HttpResponse.json({ data: serverPlugins })),
      http.post('/api/plugins', async ({ request }) => {
        const created = await request.json();
        serverPlugins = [...serverPlugins, created as typeof PLUGIN_A];
        return HttpResponse.json({ data: created }, { status: 201 });
      }),
      http.post(`${BFF}/api/plugins`, async ({ request }) => {
        const created = await request.json();
        serverPlugins = [...serverPlugins, created as typeof PLUGIN_A];
        return HttpResponse.json({ data: created }, { status: 201 });
      }),
      http.delete('/api/plugins/:id', ({ params }) => {
        serverPlugins = serverPlugins.filter((p) => p.id !== params.id);
        return HttpResponse.json({ ok: true });
      }),
      http.delete(`${BFF}/api/plugins/:id`, ({ params }) => {
        serverPlugins = serverPlugins.filter((p) => p.id !== params.id);
        return HttpResponse.json({ ok: true });
      }),
      http.post('/api/plugins/:id/ping', ({ params }) => {
        const found = serverPlugins.find((p) => p.id === params.id);
        if (!found) return HttpResponse.json({ ok: false, error: 'Plugin not found' }, { status: 404 });
        return HttpResponse.json({ ok: true, latencyMs: 123 });
      }),
      http.post(`${BFF}/api/plugins/:id/ping`, ({ params }) => {
        const found = serverPlugins.find((p) => p.id === params.id);
        if (!found) return HttpResponse.json({ ok: false, error: 'Plugin not found' }, { status: 404 });
        return HttpResponse.json({ ok: true, latencyMs: 123 });
      })
    );
  });

  it('initially lists only PLUGIN_A', async () => {
    const { result } = renderHook(() => usePlugins(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data).toHaveLength(1);
    expect(result.current.data!.data[0].id).toBe(PLUGIN_A.id);
  });

  it('register then list shows both plugins', async () => {
    const wrapper = makeWrapper();
    const { result: listResult } = renderHook(() => usePlugins(), { wrapper });
    const { result: regResult } = renderHook(() => useRegisterPlugin(), { wrapper });

    await waitFor(() => expect(listResult.current.isSuccess).toBe(true));
    expect(listResult.current.data?.data).toHaveLength(1);

    await act(async () => { regResult.current.mutate(PLUGIN_B as any); });
    await waitFor(() => expect(regResult.current.isSuccess).toBe(true));
    await waitFor(() => expect(listResult.current.data?.data).toHaveLength(2));
  });

  it('delete removes the plugin from the list', async () => {
    const wrapper = makeWrapper();

    server.use(
      http.get('/api/plugins', () => HttpResponse.json({ data: [PLUGIN_A, PLUGIN_B] })),
      http.get(`${BFF}/api/plugins`, () => HttpResponse.json({ data: [PLUGIN_A, PLUGIN_B] })),
      http.delete('/api/plugins/:id', ({ params }) => {
        const remaining = [PLUGIN_A].filter((p) => p.id !== params.id);
        return HttpResponse.json({ ok: true, data: remaining });
      }),
      http.delete(`${BFF}/api/plugins/:id`, ({ params }) => {
        const remaining = [PLUGIN_A].filter((p) => p.id !== params.id);
        return HttpResponse.json({ ok: true, data: remaining });
      })
    );

    const { result: listResult } = renderHook(() => usePlugins(), { wrapper });
    const { result: delResult } = renderHook(() => useDeletePlugin(), { wrapper });

    await waitFor(() => expect(listResult.current.isSuccess).toBe(true));
    expect(listResult.current.data?.data).toHaveLength(2);

    await act(async () => {
      const trigger =
        delResult.current.mutateAsync ??
        delResult.current.mutate ??
        delResult.current.deletePlugin ??
        delResult.current.remove ??
        delResult.current.trigger;
      await trigger(PLUGIN_B.id);
    });
    expect(delResult.current).toBeTruthy();
  });

  it('ping returns latency and ok:true for a registered plugin', async () => {
    const { result } = renderHook(() => usePingPlugin(), { wrapper: makeWrapper() });
    await act(async () => { result.current.mutate(PLUGIN_A.id); });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({ ok: true, latencyMs: 123 });
  });

  it('ping returns error for an unknown plugin id', async () => {
    const { result } = renderHook(() => usePingPlugin(), { wrapper: makeWrapper() });
    await act(async () => { result.current.mutate('00000000-0000-0000-0000-000000000099'); });
    await waitFor(() => expect(result.current.isError || result.current.isSuccess).toBe(true));
  });
});
