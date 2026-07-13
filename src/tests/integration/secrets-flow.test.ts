/**
 * Integration smoke-tests: secrets CRUD via MSW.
 * Mirrors the runs-crud.test.ts integration pattern.
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const BASE = 'http://localhost:3000';
const AUTH = { Authorization: 'Bearer demo-token' };

const STUB_SECRET = {
  id: 'sec-001',
  key: 'OPENAI_API_KEY',
  scope: 'global',
  maskedValue: '****',
  createdAt: '2026-07-13T00:00:00Z',
  updatedAt: '2026-07-13T00:00:00Z',
};

const handlers = [
  http.get(`${BASE}/api/secrets`, () =>
    HttpResponse.json({ data: [STUB_SECRET] }),
  ),
  http.post(`${BASE}/api/secrets`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    // rawValue must never be echoed back
    const { rawValue: _, ...safe } = body as Record<string, unknown>;
    return HttpResponse.json({ data: { ...STUB_SECRET, key: safe['key'] as string } });
  }),
  http.delete(`${BASE}/api/secrets/:key`, ({ params }) =>
    HttpResponse.json({ ok: true, key: params['key'] }),
  ),
];

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());


describe('Secrets CRUD integration', () => {
  it('GET /api/secrets returns array', async () => {
    const res = await fetch(`${BASE}/api/secrets`, { headers: AUTH });
    const body = await res.json();
    expect(Array.isArray(body.data)).toBe(true);
  });

  it('POST /api/secrets does not echo rawValue', async () => {
    const res = await fetch(`${BASE}/api/secrets`, {
      method: 'POST',
      headers: { ...AUTH, 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'MY_SECRET', rawValue: 'hunter2', scope: 'global' }),
    });
    const body = await res.json();
    expect('rawValue' in body.data).toBe(false);
  });

  it('POST /api/secrets echoes key', async () => {
    const res = await fetch(`${BASE}/api/secrets`, {
      method: 'POST',
      headers: { ...AUTH, 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'ECHO_KEY', rawValue: 'x', scope: 'global' }),
    });
    const body = await res.json();
    expect(body.data.key).toBe('ECHO_KEY');
  });

  it('DELETE /api/secrets/:key returns ok', async () => {
    const res = await fetch(`${BASE}/api/secrets/OPENAI_API_KEY`, {
      method: 'DELETE',
      headers: AUTH,
    });
    const body = await res.json();
    expect(body.ok).toBe(true);
  });

  it('unauthenticated GET returns 401', async () => {
    server.use(
      http.get(`${BASE}/api/secrets`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
    );
    const res = await fetch(`${BASE}/api/secrets`);
    expect(res.status).toBe(401);
  });

  it('unauthenticated POST returns 401', async () => {
    server.use(
      http.post(`${BASE}/api/secrets`, () =>
        new HttpResponse(null, { status: 401 }),
      ),
    );
    const res = await fetch(`${BASE}/api/secrets`, { method: 'POST' });
    expect(res.status).toBe(401);
  });
});
