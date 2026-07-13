/**
 * src/lib/api/index.ts
 *
 * Barrel export for the BFF API client layer.
 */
export { bffGet, bffPost, bffPatch, bffDelete, bffDownload } from './client';
export { ApiError, isNotFound, isUnauthorized, isForbidden, isServerError, isApiError, parseApiError } from './errors';
export { unwrap } from './response';
export type { ApiResult, PaginatedList, PaginatedResult } from './response';
export { ENDPOINTS } from './endpoints';
