/**
 * src/lib/api/client.ts
 *
 * Type-safe BFF HTTP client.
 *
 * All frontend → BFF communication goes through these helpers.
 * Never use raw fetch() in components or features.
 *
 * Canonical BFF port: 8081
 * Ref: Forge-OH-Build-Plan-Definitive.md § Architecture
 */
import { ApiError, parseApiError } from './errors';
import type { ApiResult } from './response';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Base URL for the Forge BFF.
 *
 * Uses NEXT_PUBLIC_BFF_URL — the same variable used by bff-client.ts and
 * MSW handlers, so dev, test, and production all share a single env var.
 * Default port 8081 is the canonical BFF port for this project.
 */
const BFF_BASE =
  process.env.NEXT_PUBLIC_BFF_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8081');

// ---------------------------------------------------------------------------
// Internal fetch wrapper
// ---------------------------------------------------------------------------

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: HeadersInit,
): Promise<ApiResult<T>> {
  const url = path.startsWith('http') ? path : `${BFF_BASE}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...Object.fromEntries(new Headers(extraHeaders ?? {}).entries()),
  };

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: 'include',
    });
  } catch (networkErr) {
    return {
      ok: false,
      error: new ApiError(
        0,
        'NETWORK_ERROR',
        networkErr instanceof Error ? networkErr.message : 'Network request failed',
      ),
    };
  }

  if (!res.ok) {
    return { ok: false, error: await parseApiError(res) };
  }

  // 204 No Content — return empty object
  if (res.status === 204) {
    return { ok: true, data: {} as T };
  }

  try {
    const data: T = await res.json();
    return { ok: true, data };
  } catch {
    return {
      ok: false,
      error: new ApiError(res.status, 'PARSE_ERROR', 'Failed to parse response JSON'),
    };
  }
}

// ---------------------------------------------------------------------------
// Public HTTP helpers
// ---------------------------------------------------------------------------

export function bffGet<T>(path: string): Promise<ApiResult<T>> {
  return request<T>('GET', path);
}

export function bffPost<T>(
  path: string,
  body?: unknown,
): Promise<ApiResult<T>> {
  return request<T>('POST', path, body);
}

export function bffPatch<T>(
  path: string,
  body?: unknown,
): Promise<ApiResult<T>> {
  return request<T>('PATCH', path, body);
}

export function bffDelete<T = Record<string, never>>(
  path: string,
): Promise<ApiResult<T>> {
  return request<T>('DELETE', path);
}

// ---------------------------------------------------------------------------
// Raw binary download (for patch exports, artifacts)
// ---------------------------------------------------------------------------

export async function bffDownload(path: string): Promise<Blob> {
  const url = path.startsWith('http') ? path : `${BFF_BASE}${path}`;
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw await parseApiError(res);
  return res.blob();
}
