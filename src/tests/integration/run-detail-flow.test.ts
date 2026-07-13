/**
 * src/tests/integration/run-detail-flow.test.ts
 *
 * Integration tests for the Run Detail API flow via MSW.
 * Covers the full lifecycle of an in-progress run:
 *   fetch run, fetch events, pause, resume, stop, fork, approve.
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { mockRuns } from '../fixtures/runs.fixture';
import { mockEvents } from '../fixtures/events.fixture';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';
const RUN = mockRuns[0];

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('GET /api/runs/:runId', () => {
  it('returns the run with expected fields', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}`);
    expect(res.ok).toBe(true);
    const { data } = await res.json();
    expect(data).toHaveProperty('id', RUN.id);
    expect(data).toHaveProperty('status');
    expect(data).toHaveProperty('title');
  });

  it('returns 404 for unknown run id', async () => {
    server.use(
      http.get(`${BFF}/api/runs/:runId`, ({ params }) => {
        if (params.runId === 'nonexistent') return new HttpResponse(null, { status: 404 });
        return HttpResponse.json({ data: RUN });
      })
    );
    const res = await fetch(`${BFF}/api/runs/nonexistent`);
    expect(res.status).toBe(404);
  });
});

describe('GET /api/runs/:runId/events', () => {
  it('returns events array', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/events`);
    expect(res.ok).toBe(true);
    const { data } = await res.json();
    expect(Array.isArray(data)).toBe(true);
  });

  it('each event has id, type, timestamp', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/events`);
    const { data } = await res.json();
    for (const evt of data.slice(0, 3)) {
      expect(evt).toHaveProperty('id');
      expect(evt).toHaveProperty('type');
      expect(evt).toHaveProperty('timestamp');
    }
  });
});

describe('POST /api/runs/:runId/pause', () => {
  it('returns ok: true', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/pause`, { method: 'POST' });
    expect(res.ok).toBe(true);
    expect((await res.json()).ok).toBe(true);
  });
});

describe('POST /api/runs/:runId/resume', () => {
  it('returns ok: true', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/resume`, { method: 'POST' });
    expect(res.ok).toBe(true);
    expect((await res.json()).ok).toBe(true);
  });
});

describe('POST /api/runs/:runId/stop', () => {
  it('returns ok: true', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/stop`, { method: 'POST' });
    expect(res.ok).toBe(true);
    expect((await res.json()).ok).toBe(true);
  });

  it('401 when no auth header (handler override)', async () => {
    server.use(
      http.post(`${BFF}/api/runs/:runId/stop`, ({ request }) => {
        if (!request.headers.get('Authorization')) {
          return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({ ok: true });
      })
    );
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/stop`, { method: 'POST' });
    expect(res.status).toBe(401);
  });
});

describe('POST /api/runs/:runId/fork', () => {
  it('returns ok and forked_id', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/fork`, { method: 'POST' });
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(body).toHaveProperty('forked_id');
    expect(body).toHaveProperty('run_id');
  });
});

describe('POST /api/runs/:runId/approve', () => {
  it('returns ok: true', async () => {
    const res = await fetch(`${BFF}/api/runs/${RUN.id}/approve`, { method: 'POST' });
    expect(res.ok).toBe(true);
    expect((await res.json()).ok).toBe(true);
  });
});
