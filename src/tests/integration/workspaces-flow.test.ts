/**
 * src/tests/integration/workspaces-flow.test.ts
 *
 * Integration tests for the Workspaces API flow via MSW.
 * Mirrors the pattern established in runs-crud.test.ts.
 *
 * Covers:
 * — GET /api/workspaces returns list
 * — GET /api/workspaces/:id returns workspace by id
 * — GET /api/workspaces/:id with unknown id returns 404 (via handler override)
 * — POST /api/workspaces/:id/reset returns ok
 * — Unauthenticated list returns 401 (via handler override)
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { mockWorkspaces } from '../fixtures/workspaces.fixture';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('GET /api/workspaces', () => {
  it('returns an array of workspaces', async () => {
    const res = await fetch(`${BFF}/api/workspaces`);
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.data.length).toBeGreaterThan(0);
  });

  it('each workspace has id, name, and status fields', async () => {
    const res = await fetch(`${BFF}/api/workspaces`);
    const { data } = await res.json();
    for (const ws of data) {
      expect(ws).toHaveProperty('id');
      expect(ws).toHaveProperty('name');
      expect(ws).toHaveProperty('status');
    }
  });

  it('returns 401 when auth header missing (handler override)', async () => {
    server.use(
      http.get(`${BFF}/api/workspaces`, ({ request }) => {
        if (!request.headers.get('Authorization')) {
          return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
        }
        return HttpResponse.json({ data: mockWorkspaces });
      })
    );
    const res = await fetch(`${BFF}/api/workspaces`);
    expect(res.status).toBe(401);
  });
});

describe('GET /api/workspaces/:id', () => {
  it('returns the first mock workspace by id', async () => {
    const id = mockWorkspaces[0].id;
    const res = await fetch(`${BFF}/api/workspaces/${id}`);
    expect(res.ok).toBe(true);
    const { data } = await res.json();
    expect(data.id).toBe(id);
  });

  it('returns 404 for unknown workspace id', async () => {
    server.use(
      http.get(`${BFF}/api/workspaces/:id`, ({ params }) => {
        const ws = mockWorkspaces.find(w => w.id === params.id);
        if (!ws) return new HttpResponse(null, { status: 404 });
        return HttpResponse.json({ data: ws });
      })
    );
    const res = await fetch(`${BFF}/api/workspaces/nonexistent-id-xyz`);
    expect(res.status).toBe(404);
  });
});

describe('POST /api/workspaces/:id/reset', () => {
  it('returns ok: true', async () => {
    const id = mockWorkspaces[0].id;
    const res = await fetch(`${BFF}/api/workspaces/${id}/reset`, { method: 'POST' });
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(body.ok).toBe(true);
  });

  it('returns 404 for unknown workspace id (handler override)', async () => {
    server.use(
      http.post(`${BFF}/api/workspaces/:id/reset`, ({ params }) => {
        const ws = mockWorkspaces.find(w => w.id === params.id);
        if (!ws) return new HttpResponse(null, { status: 404 });
        return HttpResponse.json({ ok: true });
      })
    );
    const res = await fetch(`${BFF}/api/workspaces/bad-id/reset`, { method: 'POST' });
    expect(res.status).toBe(404);
  });
});
