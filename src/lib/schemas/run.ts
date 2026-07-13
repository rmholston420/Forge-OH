import { z } from 'zod';

export const RunStatusSchema = z.enum([
  'idle',
  'running',
  'streaming',
  'queued',
  'paused',
  'awaiting_approval',
  'succeeded',
  'failed',
  'blocked',
]);

export type RunStatus = z.infer<typeof RunStatusSchema>;

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'remote_api']);

export const RunSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  status: RunStatusSchema,
  agentPresetName: z.string(),
  workspaceId: z.string(),
  workspaceType: WorkspaceTypeSchema,
  activeTool: z.string().nullable(),
  updatedAt: z.string().datetime(),
  createdAt: z.string().datetime(),
  elapsedMs: z.number().nullable(),
  estimatedCostUsd: z.number().nullable(),
});

export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunDetailSchema = RunSummarySchema.extend({
  taskPrompt: z.string(),
  model: z.string(),
  eventCount: z.number().int().nonnegative(),
  artifactCount: z.number().int().nonnegative(),
  planNodeCount: z.number().int().nonnegative(),
});

export type RunDetail = z.infer<typeof RunDetailSchema>;

export const CreateRunRequestSchema = z.object({
  taskPrompt: z.string().min(1),
  agentPresetId: z.string(),
  workspaceId: z.string(),
});

export type CreateRunRequest = z.infer<typeof CreateRunRequestSchema>;
