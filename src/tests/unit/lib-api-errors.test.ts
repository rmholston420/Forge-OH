/**
 * src/tests/unit/lib-api-errors.test.ts
 *
 * Covers ApiError construction, all type-guards, and every branch of
 * parseApiError (JSON body / non-JSON body / partial fields).
 */
import { describe, it, expect } from 'vitest';
import {
  ApiError,
  parseApiError,
  isApiError,
  isNotFound,
  isUnauthorized,
  isForbidden,
  isServerError,
} from '@/lib/api/errors';

describe('ApiError', () => {
  it('constructs with status/code/detail and human message', () => {
    const e = new ApiError(404, 'RUN_NOT_FOUND', 'run missing');
    expect(e).toBeInstanceOf(Error);
    expect(e).toBeInstanceOf(ApiError);
    expect(e.name).toBe('ApiError');
    expect(e.status).toBe(404);
    expect(e.code).toBe('RUN_NOT_FOUND');
    expect(e.detail).toBe('run missing');
    expect(e.message).toBe('[404] RUN_NOT_FOUND: run missing');
  });
});

describe('type guards', () => {
  const mk = (s: number) => new ApiError(s, 'X', 'y');
  it('isApiError', () => {
    expect(isApiError(mk(500))).toBe(true);
    expect(isApiError(new Error('x'))).toBe(false);
    expect(isApiError('nope')).toBe(false);
    expect(isApiError(null)).toBe(false);
  });
  it('isNotFound / isUnauthorized / isForbidden', () => {
    expect(isNotFound(mk(404))).toBe(true);
    expect(isNotFound(mk(500))).toBe(false);
    expect(isUnauthorized(mk(401))).toBe(true);
    expect(isForbidden(mk(403))).toBe(true);
    expect(isForbidden(mk(401))).toBe(false);
  });
  it('isServerError — every 5xx', () => {
    expect(isServerError(mk(500))).toBe(true);
    expect(isServerError(mk(599))).toBe(true);
    expect(isServerError(mk(499))).toBe(false);
    expect(isServerError('nope' as unknown)).toBe(false);
  });
});

describe('parseApiError', () => {
  it('extracts code + detail from JSON body', async () => {
    const res = new Response(
      JSON.stringify({ code: 'RATE_LIMIT', detail: 'slow down' }),
      { status: 429, statusText: 'Too Many' },
    );
    const err = await parseApiError(res);
    expect(err.status).toBe(429);
    expect(err.code).toBe('RATE_LIMIT');
    expect(err.detail).toBe('slow down');
  });
  it('accepts legacy {error, message} shape', async () => {
    const res = new Response(
      JSON.stringify({ error: 'BAD_REQUEST', message: 'nope' }),
      { status: 400 },
    );
    const err = await parseApiError(res);
    expect(err.code).toBe('BAD_REQUEST');
    expect(err.detail).toBe('nope');
  });
  it('falls back to UNKNOWN_ERROR + statusText when body is not JSON', async () => {
    const res = new Response('not json here', {
      status: 500,
      statusText: 'Server Explode',
    });
    const err = await parseApiError(res);
    expect(err.status).toBe(500);
    expect(err.code).toBe('UNKNOWN_ERROR');
    expect(err.detail).toBe('Server Explode');
  });
  it('handles partial JSON (only detail)', async () => {
    const res = new Response(JSON.stringify({ detail: 'partial' }), { status: 418 });
    const err = await parseApiError(res);
    expect(err.code).toBe('UNKNOWN_ERROR');
    expect(err.detail).toBe('partial');
  });
});
