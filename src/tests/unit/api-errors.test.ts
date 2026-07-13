/**
 * src/tests/unit/api-errors.test.ts
 *
 * Covers: src/lib/api/errors.ts
 * — ApiError class construction & properties
 * — All five type-guard helpers
 */
import { describe, it, expect } from 'vitest';
import {
  ApiError,
  isNotFound,
  isUnauthorized,
  isForbidden,
  isServerError,
  isApiError,
} from '@/lib/api/errors';

describe('ApiError', () => {
  it('sets all properties on construction', () => {
    const e = new ApiError(422, 'VALIDATION_ERROR', 'field required');
    expect(e.status).toBe(422);
    expect(e.code).toBe('VALIDATION_ERROR');
    expect(e.detail).toBe('field required');
    expect(e.name).toBe('ApiError');
    expect(e).toBeInstanceOf(Error);
    expect(e).toBeInstanceOf(ApiError);
  });

  it('message format includes status, code, detail', () => {
    const e = new ApiError(404, 'NOT_FOUND', 'run not found');
    expect(e.message).toBe('[404] NOT_FOUND: run not found');
  });

  it('is throwable and catchable as Error', () => {
    expect(() => { throw new ApiError(500, 'SERVER_ERROR', 'oops'); })
      .toThrow(Error);
  });
});

describe('type guards', () => {
  const make = (status: number) => new ApiError(status, 'CODE', 'detail');

  describe('isApiError', () => {
    it('returns true for ApiError instances', () => {
      expect(isApiError(make(400))).toBe(true);
    });
    it('returns false for plain Error', () => {
      expect(isApiError(new Error('plain'))).toBe(false);
    });
    it('returns false for null / undefined', () => {
      expect(isApiError(null)).toBe(false);
      expect(isApiError(undefined)).toBe(false);
    });
    it('returns false for string', () => {
      expect(isApiError('error string')).toBe(false);
    });
  });

  describe('isNotFound', () => {
    it('true for 404', () => expect(isNotFound(make(404))).toBe(true));
    it('false for 403', () => expect(isNotFound(make(403))).toBe(false));
    it('false for non-ApiError', () => expect(isNotFound(new Error())).toBe(false));
  });

  describe('isUnauthorized', () => {
    it('true for 401', () => expect(isUnauthorized(make(401))).toBe(true));
    it('false for 403', () => expect(isUnauthorized(make(403))).toBe(false));
  });

  describe('isForbidden', () => {
    it('true for 403', () => expect(isForbidden(make(403))).toBe(true));
    it('false for 401', () => expect(isForbidden(make(401))).toBe(false));
  });

  describe('isServerError', () => {
    it('true for 500', () => expect(isServerError(make(500))).toBe(true));
    it('true for 503', () => expect(isServerError(make(503))).toBe(true));
    it('false for 499', () => expect(isServerError(make(499))).toBe(false));
    it('false for 404', () => expect(isServerError(make(404))).toBe(false));
  });
});
