import { z } from 'zod';

// ISO-8601 datetime — accepts both Z-suffix ("2026-07-13T00:00:00Z") and
// numeric offset ("2026-07-13T00:00:00+00:00"). z.string().datetime() rejects
// Z-suffix in some Zod versions, so we use a permissive regex instead.
const isoDatetime = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/,
    'Expected ISO-8601 datetime string',
  );

export const RunStatusSchema = z.enum([
  'idle',
  'running',
  'streaming',
  'queued',
  'paused',
  'awaiting-approval',
  'disconnected',
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
  workspaceType: z.enum(['local', 'docker', 'remote-api']),
  activeTool: z.string().nullable(),
  updatedAt: isoDatetime,
  createdAt: isoDatetime,
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

// BFF list envelope: { data: [...], pageInfo: { total, page, pageSize } }
export const RunListResponseSchema = z.object({
  data: z.array(RunSummarySchema),
  pageInfo: z.object({
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type RunListResponse = z.infer<typeof RunListResponseSchema>;

// Canonical create-run request shape — aligns with BFF CreateRunRequest.
// Single source of truth: features/runs/schemas.ts re-exports this type.
export const CreateRunRequestSchema = z.object({
  title: z.string().min(1, 'Task description is required'),
  agentPresetId: z.string().min(1),
  workspaceId: z.string().min(1),
  taskPrompt: z.string().optional(),
  taskComplexity: z.enum(['simple', 'agentic']).default('agentic'),
  contextLength: z.number().int().nonnegative().optional(),
});

export type CreateRunRequest = z.infer<typeof CreateRunRequestSchema>;
