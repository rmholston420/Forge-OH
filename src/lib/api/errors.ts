/**
 * src/lib/api/errors.ts
 *
 * Typed error classes for BFF API communication.
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § lib/api/
 */

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;

  constructor(status: number, code: string, detail: string) {
    super(`[${status}] ${code}: ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// HTTP status helpers
// ---------------------------------------------------------------------------

export const isNotFound = (e: unknown): e is ApiError =>
  e instanceof ApiError && e.status === 404;

export const isUnauthorized = (e: unknown): e is ApiError =>
  e instanceof ApiError && e.status === 401;

export const isForbidden = (e: unknown): e is ApiError =>
  e instanceof ApiError && e.status === 403;

export const isServerError = (e: unknown): e is ApiError =>
  e instanceof ApiError && e.status >= 500;

export const isApiError = (e: unknown): e is ApiError =>
  e instanceof ApiError;

// ---------------------------------------------------------------------------
// Parse error from fetch Response
// ---------------------------------------------------------------------------

export async function parseApiError(res: Response): Promise<ApiError> {
  let code = 'UNKNOWN_ERROR';
  let detail = res.statusText;
  try {
    const body = await res.json();
    code = body?.code ?? body?.error ?? code;
    detail = body?.detail ?? body?.message ?? detail;
  } catch {
    // body is not JSON — use statusText
  }
  return new ApiError(res.status, code, detail);
}
