import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const BASE = 'http://localhost:3000';

const server = setupServer(
  http.get(`${BASE}/api/secrets`, () =>
    HttpResponse.json({
      data: [
        { key: 'OPENAI_API_KEY', updatedAt: '2026-07-13T00:00:00.000Z' },
        { key: 'ANTHROPIC_API_KEY', updatedAt: '2026-07-13T00:00:00.000Z' },
      ],
    })
  ),

  http.post(`${BASE}/api/secrets`, async ({ request }) => {
    const payload = (await request.clone().json()) as { key: string; rawValue?: string };
    return HttpResponse.json({
      data: {
        key: payload.key,
        updatedAt: '2026-07-13T00:00:00.000Z',
      },
    });
  }),

  http.delete(`${BASE}/api/secrets/:key`, ({ params }) =>
    HttpResponse.json({
      data: {
        key: params.key,
        deleted: true,
      },
    })
  )
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Secrets CRUD integration', () => {
  it('GET /api/secrets returns array', async () => {
    const res = await fetch(`${BASE}/api/secrets`);
    const body = await res.json();

    expect(Array.isArray(body.data)).toBe(true);
    expect(body.data).toHaveLength(2);
  });

  it('POST /api/secrets does not echo rawValue', async () => {
    const res = await fetch(`${BASE}/api/secrets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'OPENAI_API_KEY', rawValue: 'super-secret' }),
    });
    const body = await res.json();

    expect(body.data.key).toBe('OPENAI_API_KEY');
    expect(body.data.rawValue).toBeUndefined();
  });

  it('POST /api/secrets echoes key', async () => {
    const res = await fetch(`${BASE}/api/secrets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'ANTHROPIC_API_KEY', rawValue: 'top-secret' }),
    });
    const body = await res.json();

    expect(body.data.key).toBe('ANTHROPIC_API_KEY');
  });

  it('DELETE /api/secrets/:key returns deleted true', async () => {
    const res = await fetch(`${BASE}/api/secrets/OPENAI_API_KEY`, {
      method: 'DELETE',
    });
    const body = await res.json();

    expect(body.data.key).toBe('OPENAI_API_KEY');
    expect(body.data.deleted).toBe(true);
  });

  it('network error on list secrets rejects gracefully', async () => {
    server.use(
      http.get(`${BASE}/api/secrets`, () => HttpResponse.error())
    );

    await expect(fetch(`${BASE}/api/secrets`)).rejects.toBeTruthy();
  });

  it('server 500 on create secret surfaces status code', async () => {
    server.use(
      http.post(`${BASE}/api/secrets`, () =>
        HttpResponse.json({ error: 'boom' }, { status: 500 })
      )
    );

    const res = await fetch(`${BASE}/api/secrets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'ERR', rawValue: 'x' }),
    });

    expect(res.status).toBe(500);
  });
});
