/**
 * src/features/inference-backends/api.ts
 *
 * BFF calls for the inference-backend health inventory.
 * Uses the canonical bffGet/unwrap helpers — never raw fetch.
 */
import { bffGet } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { unwrap } from '@/lib/api/response';
import type { InferenceBackend } from './schemas';

export async function fetchInferenceBackends(): Promise<InferenceBackend[]> {
  const result = await bffGet<{ data: InferenceBackend[] }>(
    ENDPOINTS.INFERENCE_BACKENDS.list(),
  );
  return unwrap(result).data;
}
