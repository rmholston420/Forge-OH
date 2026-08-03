/**
 * src/tests/unit/lib-api-client.test.ts
 *
 * Exercises every branch of the type-safe BFF client:
 *   - request success path (200 JSON)
 *   - 204 No Content shortcut
 *   - HTTP error path via parseApiError
 *   - network / fetch throw path
 *   - JSON parse failure path
 *   - method helpers: bffGet / bffPost / bffPatch / bffDelete
 *   - bffDownload success + failure paths
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import {
  bffGet,
  bffPost,
  bffPatch,
  bffDelete,
  bffDownload,
} from '@/lib/api/client';
import { ApiError } from '@/lib/api/errors';

const BFF = 'http://localhost:8081';

describe('bff HTTP client', () => {
  beforeEach(() => {
    server.resetHandlers();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('bffGet returns ok:true on 200 JSON', async () => {
    server.use(
      http.get(`${BFF}/ping`, () => HttpResponse.json({ hello: 'world' })),
    );
    const r = await bffGet<{ hello: string }>('/ping');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data.hello).toBe('world');
  });

  it('bffPost sends JSON body', async () => {
    server.use(
      http.post(`${BFF}/echo`, async ({ request }) => {
        const body = await request.json();
        return HttpResponse.json({ echoed: body });
      }),
    );
    const r = await bffPost<{ echoed: { a: number } }>('/echo', { a: 1 });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data.echoed).toEqual({ a: 1 });
  });

  it('bffPatch works and returns parsed body', async () => {
    server.use(
      http.patch(`${BFF}/thing/1`, () => HttpResponse.json({ patched: true })),
    );
    const r = await bffPatch<{ patched: boolean }>('/thing/1', { name: 'x' });
    expect(r.ok && r.data.patched).toBe(true);
  });

  it('bffDelete returns empty object on 204', async () => {
    server.use(
      http.delete(`${BFF}/thing/1`, () => new Response(null, { status: 204 })),
    );
    const r = await bffDelete('/thing/1');
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data).toEqual({});
  });

  it('non-2xx returns ApiError from parseApiError', async () => {
    server.use(
      http.get(`${BFF}/missing`, () =>
        HttpResponse.json({ code: 'NOT_FOUND', detail: 'gone' }, { status: 404 }),
      ),
    );
    const r = await bffGet('/missing');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.error).toBeInstanceOf(ApiError);
      expect(r.error.status).toBe(404);
      expect(r.error.code).toBe('NOT_FOUND');
    }
  });

  it('network error → NETWORK_ERROR ApiError', async () => {
    // Force fetch to throw
    const origFetch = globalThis.fetch;
    (globalThis as any).fetch = vi.fn(() => {
      throw new Error('boom');
    });
    const r = await bffGet('/anywhere');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.error.status).toBe(0);
      expect(r.error.code).toBe('NETWORK_ERROR');
      expect(r.error.detail).toContain('boom');
    }
    (globalThis as any).fetch = origFetch;
  });

  it('JSON parse failure → PARSE_ERROR ApiError', async () => {
    server.use(
      http.get(`${BFF}/bad-json`, () =>
        new Response('not-json', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    const r = await bffGet('/bad-json');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.error.code).toBe('PARSE_ERROR');
      expect(r.error.status).toBe(200);
    }
  });

  it('accepts absolute URL passthrough', async () => {
    server.use(
      http.get('http://other.host/absolute', () => HttpResponse.json({ pass: 1 })),
    );
    const r = await bffGet<{ pass: number }>('http://other.host/absolute');
    expect(r.ok && r.data.pass).toBe(1);
  });
});

describe('bffDownload', () => {
  beforeEach(() => server.resetHandlers());

  it('returns Blob on success', async () => {
    server.use(
      http.get(`${BFF}/artifact.bin`, () =>
        new Response('binary-bytes', { status: 200 }),
      ),
    );
    const blob = await bffDownload('/artifact.bin');
    // jsdom Blob implements the constructor + size/type but not
    // text() / arrayBuffer() in older versions — assert shape only.
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBeGreaterThan(0);
  });

  it('throws ApiError on non-2xx', async () => {
    server.use(
      http.get(`${BFF}/artifact.bin`, () =>
        HttpResponse.json({ code: 'GONE', detail: 'nope' }, { status: 410 }),
      ),
    );
    await expect(bffDownload('/artifact.bin')).rejects.toBeInstanceOf(ApiError);
  });
});
