/**
 * src/features/inference-backends/schemas.ts
 *
 * Frontend mirror of bff/services/inference_backends/types.py.
 * Vocabulary is byte-for-byte identical to the BFF response — the UI
 * never translates state names, so a `healthy | degraded | unhealthy |
 * muted` shows up here exactly as the backend reports it.
 */
import { z } from 'zod';
import { BackendIdSchema } from '@/lib/schemas/run';

// Re-export the canonical BackendId schema/type so consumers under
// features/inference-backends only need this one import path.
export { BackendIdSchema };
export type BackendId = z.infer<typeof BackendIdSchema>;

export const HealthStateSchema = z.enum(['healthy', 'degraded', 'unhealthy', 'muted']);
export type HealthState = z.infer<typeof HealthStateSchema>;

export const RoleHintSchema = z.enum(['coder', 'planner', 'any', 'probe']);
export type RoleHint = z.infer<typeof RoleHintSchema>;

export const BackendHealthSchema = z.object({
  state:      HealthStateSchema,
  latencyMs:  z.number().int().nonnegative().nullable(),
  modelCount: z.number().int().nonnegative().nullable(),
  error:      z.string().nullable(),
});
export type BackendHealth = z.infer<typeof BackendHealthSchema>;

export const InferenceBackendSchema = z.object({
  id:                BackendIdSchema,
  displayName:       z.string(),
  baseUrl:           z.string(),
  supportsStreaming: z.boolean(),
  roleHint:          RoleHintSchema,
  health:            BackendHealthSchema,
});
export type InferenceBackend = z.infer<typeof InferenceBackendSchema>;

// Wire envelope from GET /api/inference-backends
export const InferenceBackendsResponseSchema = z.object({
  data: z.array(InferenceBackendSchema),
});
export type InferenceBackendsResponse = z.infer<typeof InferenceBackendsResponseSchema>;
