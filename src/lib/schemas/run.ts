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

export const RunSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  status: RunStatusSchema,
  agentPresetName: z.string(),
  workspaceId: z.string(),
  workspaceType: z.enum(['local', 'docker', 'remote_api']),
  activeTool: z.string().nullable(),
  updatedAt: z.string().datetime(),
  createdAt: z.string().datetime(),
  elapsedMs: z.number().nullable(),
  estimatedCostUsd: z.number().nullable(),
});

export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunDetailSchema = RunSummarySchema.extend({
  taskPrompt: z.string(),
  modelName: z.string().optional(),
  contextTokens: z.number().optional(),
  totalEvents: z.number().optional(),
  totalArtifacts: z.number().optional(),
  totalCommands: z.number().optional(),
});

export type RunDetail = z.infer<typeof RunDetailSchema>;

export const RunListResponseSchema = z.object({
  runs: z.array(RunSummarySchema),
  total: z.number(),
  page: z.number().optional(),
  pageSize: z.number().optional(),
});

export type RunListResponse = z.infer<typeof RunListResponseSchema>;

export const CreateRunRequestSchema = z.object({
  taskPrompt: z.string().min(1),
  agentPresetId: z.string(),
  workspaceId: z.string(),
  title: z.string().optional(),
});

export type CreateRunRequest = z.infer<typeof CreateRunRequestSchema>;
