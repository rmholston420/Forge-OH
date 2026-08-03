/**
 * Zod schema for TrajectoryRecord, mirroring
 * `openhands_tools_ext/trajectory/schema.py`.
 *
 * A `TrajectoryRecord` is Rec #3's storage unit — the structured,
 * embeddable memory of one completed run. The frontend consumes it via
 * the case-retrieval widget on the Overview tab.
 *
 * Parity with the Python schema is enforced by
 * `openhands_tools_ext/tests/trajectory/test_schema.py::TestFrontendParity`.
 */
import { z } from 'zod';

import { VerificationStepSchema } from './verify';

export const TrajectoryStatusSchema = z.enum([
  'success',
  'failed',
  'verified_failure',
  'aborted',
  'unknown',
]);
export type TrajectoryStatus = z.infer<typeof TrajectoryStatusSchema>;

export const TrajectoryDiffSchema = z.object({
  path: z.string(),
  lines_added: z.number().int().min(0),
  lines_removed: z.number().int().min(0),
  summary: z.string().default(''),
});
export type TrajectoryDiff = z.infer<typeof TrajectoryDiffSchema>;

export const TrajectoryRecordSchema = z.object({
  trajectory_id: z.string(),
  run_id: z.string(),
  session_id: z.string(),
  task_description: z.string(),
  plan: z.string().default(''),
  diffs: z.array(TrajectoryDiffSchema).default([]),
  verify_iterations: z.array(VerificationStepSchema).default([]),
  final_status: TrajectoryStatusSchema,
  symptom: z.string().default(''),
  repograph_repo_key: z.string().default(''),
  repograph_symbols: z.array(z.string()).default([]),
  embedding: z.array(z.number()).nullable().default(null),
  embedding_model: z.string().default(''),
  created_at: z.string(),
});
export type TrajectoryRecord = z.infer<typeof TrajectoryRecordSchema>;

/** Canonical BFF endpoint prefix for trajectory read APIs. */
export const TRAJECTORY_API_PREFIX = '/trajectories' as const;

/** Default retrieval budget (top-k) for the case-retrieval widget. */
export const DEFAULT_RETRIEVAL_K = 3;

// ---------------------------------------------------------------------------
// Search response — mirrors bff/routers/trajectories.py::SearchHit /
// SearchResponse. Parity is guarded by test_trajectories_router.py::
// TestFrontendParity.
// ---------------------------------------------------------------------------

export const TrajectorySearchHitSchema = z.object({
  record: TrajectoryRecordSchema,
  score: z.number(),
  semantic_score: z.number(),
  symbol_overlap: z.number(),
});
export type TrajectorySearchHit = z.infer<typeof TrajectorySearchHitSchema>;

export const TrajectorySearchResponseSchema = z.object({
  query: z.string(),
  k: z.number().int(),
  hits: z.array(TrajectorySearchHitSchema),
});
export type TrajectorySearchResponse = z.infer<
  typeof TrajectorySearchResponseSchema
>;

export const TrajectoryListResponseSchema = z.object({
  total: z.number().int(),
  records: z.array(TrajectoryRecordSchema),
});
export type TrajectoryListResponse = z.infer<
  typeof TrajectoryListResponseSchema
>;

export interface TrajectorySearchRequest {
  task_description: string;
  symptom?: string;
  k?: number;
  verified_only?: boolean;
  repo_key?: string;
  current_symbols?: string[];
  exclude_run_ids?: string[];
}
