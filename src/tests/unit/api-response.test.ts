/**
 * src/tests/unit/api-response.test.ts
 *
 * Covers: src/lib/api/response.ts
 * — unwrap() happy path and error propagation
 * — PaginatedList shape
 */
import { describe, it, expect } from 'vitest';
import { unwrap } from '@/lib/api/response';
import type { ApiResult, PaginatedList } from '@/lib/api/response';
import { ApiError } from '@/lib/api/errors';

describe('unwrap', () => {
  it('returns data when ok is true', () => {
    const result: ApiResult<{ id: string }> = { ok: true, data: { id: 'abc' } };
    expect(unwrap(result)).toEqual({ id: 'abc' });
  });

  it('throws ApiError when ok is false', () => {
    const err = new ApiError(404, 'NOT_FOUND', 'run not found');
    const result: ApiResult<never> = { ok: false, error: err };
    expect(() => unwrap(result)).toThrow(ApiError);
    expect(() => unwrap(result)).toThrow('NOT_FOUND');
  });

  it('thrown error preserves status', () => {
    const err = new ApiError(403, 'FORBIDDEN', 'no access');
    try {
      unwrap({ ok: false, error: err });
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).status).toBe(403);
    }
  });

  it('unwraps primitive types', () => {
    expect(unwrap<number>({ ok: true, data: 42 })).toBe(42);
    expect(unwrap<string>({ ok: true, data: 'hello' })).toBe('hello');
  });
});

describe('PaginatedList shape', () => {
  it('satisfies the expected interface', () => {
    const pl: PaginatedList<string> = {
      items: ['a', 'b'],
      total: 2,
      page: 1,
      pageSize: 20,
      hasMore: false,
    };
    expect(pl.items).toHaveLength(2);
    expect(pl.hasMore).toBe(false);
    expect(pl.total).toBe(2);
  });

  it('hasMore is true when total exceeds pageSize', () => {
    const pl: PaginatedList<number> = {
      items: [1, 2, 3],
      total: 100,
      page: 1,
      pageSize: 3,
      hasMore: true,
    };
    expect(pl.hasMore).toBe(true);
  });
});
