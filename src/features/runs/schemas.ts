/**
 * src/features/runs/schemas.ts
 *
 * Re-exports canonical schema types from lib/schemas/run.
 * Do NOT define a second CreateRunRequestSchema here — the canonical
 * definition lives in src/lib/schemas/run.ts.
 */
import { z } from 'zod';
import { RunSummarySchema, RunStatusSchema, CreateRunRequestSchema } from '@/lib/schemas/run';

export { RunSummarySchema, RunStatusSchema, CreateRunRequestSchema };
export type { RunSummary } from '@/lib/schemas/run';
export type CreateRunRequest = import('@/lib/schemas/run').CreateRunRequest;

export const AgentPresetSchema = z.object({
  id: z.string(),
  name: z.string(),
  model: z.string(),
  description: z.string().optional(),
});

export type AgentPreset = z.infer<typeof AgentPresetSchema>;

export const RunsFilterSchema = z.object({
  status: RunStatusSchema.optional(),
  // remote-api (hyphenated) — matches DOMAIN_MODEL.md and RunSummarySchema
  workspaceType: z.enum(['local', 'docker', 'remote-api']).optional(),
  search: z.string().optional(),
});

export type RunsFilter = z.infer<typeof RunsFilterSchema>;
