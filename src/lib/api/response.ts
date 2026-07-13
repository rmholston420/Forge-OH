/**
 * src/lib/api/response.ts
 *
 * Typed response wrapper for all BFF API calls.
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § lib/api/
 */
import type { ApiError } from './errors';

// ---------------------------------------------------------------------------
// Result union
// ---------------------------------------------------------------------------

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

/**
 * Unwrap an ApiResult. Throws the error if !ok.
 * Use when you want to propagate to React Error Boundary.
 */
export function unwrap<T>(result: ApiResult<T>): T {
  if (!result.ok) throw result.error;
  return result.data;
}

// ---------------------------------------------------------------------------
// Paginated list
// ---------------------------------------------------------------------------

export interface PaginatedList<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export type PaginatedResult<T> = ApiResult<PaginatedList<T>>;
