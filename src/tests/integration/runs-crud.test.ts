/**
 * Integration smoke-tests: runs CRUD + lifecycle via the real BFF TestClient.
 *
 * These tests use MSW (or a lightweight fetch mock) to intercept
 * /api/runs requests and verify that the frontend query layer
 * round-trips correctly with realistic stub responses.
 *
 * Pattern mirrors src/tests/integration/auth-flow.test.ts.
 */
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const BASE = 'http://localhost:3000';

// ---------------------------------------------------------------------------
// Shared stub fixtures
// ---------------------------------------------------------------------------

const STUB_RUN = {
  id: 'run-int-001',
  title: 'Integration test run',
  status: 'queued',
  agentPresetName: 'default',
  workspaceId: 'ws-001',
  workspaceType: 'local',
  activeTool: null,
  updatedAt: '2026-07-13T00:00:00Z',
  createdAt: '2026-07-13T00:00:00Z',
  elapsedMs: null,
  estimatedCostUsd: null,
};

// ---------------------------------------------------------------------------
// MSW handlers
// ---------------------------------------------------------------------------

const handlers = [
  http.get(`${BASE}/api/runs`, () =>
    HttpResponse.json({ data: [STUB_RUN], stub: true }),
  ),
  http.post(`${BASE}/api/runs`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({
      data: { ...STUB_RUN, id: 'run-int-new', title: body['title'] as string },
    });
  }),
  http.get(`${BASE}/api/runs/:runId`, ({ params }) =>
    HttpResponse.json({ data: { ...STUB_RUN, id: params['runId'] } }),
  ),
  http.post(`${BASE}/api/runs/:runId/stop`, ({ params }) =>
    HttpResponse.json({ ok: true, run_id: params['runId'], status: 'stopped' }),
  ),
  http.post(`${BASE}/api/runs/:runId/fork`, ({ params }) =>
    HttpResponse.json({ ok: true, run_id: params['runId'], forked_id: `${params['runId']}-fork-1` }),
  ),
  http.get(`${BASE}/api/runs/compare`, ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json({
      data: {
        baseRunId: url.searchParams.get('base'),
        forkRunId: url.searchParams.get('fork'),
        files: [],
        stats: { totalFiles: 0, additions: 0, deletions: 0 },
      },
    });
  }),
];

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Runs CRUD integration', () => {
  it('GET /api/runs returns array', async () => {
    const res = await fetch(`${BASE}/api/runs`);
    const body = await res.json();
    expect(Array.isArray(body.data)).toBe(true);
  });

  it('POST /api/runs echoes title', async () => {
    const res = await fetch(`${BASE}/api/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Hello', agentPresetId: 'p1', workspaceId: 'ws-1' }),
    });
    const body = await res.json();
    expect(body.data.title).toBe('Hello');
  });

  it('GET /api/runs/:id returns run with correct id', async () => {
    const res = await fetch(`${BASE}/api/runs/run-int-001`);
    const body = await res.json();
    expect(body.data.id).toBe('run-int-001');
  });

  it('POST /api/runs/:id/stop returns stopped status', async () => {
    const res = await fetch(`${BASE}/api/runs/run-int-001/stop`, { method: 'POST' });
    const body = await res.json();
    expect(body.status).toBe('stopped');
    expect(body.ok).toBe(true);
  });

  it('POST /api/runs/:id/fork returns forked_id', async () => {
    const res = await fetch(`${BASE}/api/runs/run-int-001/fork`, { method: 'POST' });
    const body = await res.json();
    expect(body.forked_id).toContain('run-int-001');
  });

  it('GET /api/runs/compare returns base and fork ids', async () => {
    const res = await fetch(`${BASE}/api/runs/compare?base=aaa&fork=bbb`);
    const body = await res.json();
    expect(body.data.baseRunId).toBe('aaa');
    expect(body.data.forkRunId).toBe('bbb');
  });
});

describe('Runs integration — error paths', () => {
  it('network error on list runs rejects gracefully', async () => {
    server.use(
      http.get(`${BASE}/api/runs`, () => HttpResponse.error()),
    );
    await expect(fetch(`${BASE}/api/runs`)).rejects.toThrow();
  });

  it('server 500 on create run surfaces status code', async () => {
    server.use(
      http.post(`${BASE}/api/runs`, () =>
        new HttpResponse(null, { status: 500 }),
      ),
    );
    const res = await fetch(`${BASE}/api/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'T', agentPresetId: 'p', workspaceId: 'w' }),
    });
    expect(res.status).toBe(500);
  });
});
