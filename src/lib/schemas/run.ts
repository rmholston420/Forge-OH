import { z } from 'zod';

export const RunStatusSchema = z.enum([
  'queued',
  'pending',
  'running',
  'completed',
  'failed',
  'stopped',
  'paused',
  'succeeded',
  'awaiting_approval',
  'pending_approval',
]);

export const RunSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  status: RunStatusSchema,
  agentPresetName: z.string().min(1),
  workspaceId: z.string().min(1),
  workspaceType: z.string().min(1),
  activeTool: z.unknown().nullable(),
  updatedAt: z.string(),
  createdAt: z.string(),
  elapsedMs: z.number().optional(),
  finishedAt: z.string().optional(),
  durationMs: z.number().optional(),
  costUsd: z.number().optional(),
  estimatedCostUsd: z.number().nullable().optional(),
});

export type Run = z.infer<typeof RunSchema>;

export const RunSummarySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  status: RunStatusSchema,
  agentPresetName: z.string().min(1),
  workspaceType: z.string().min(1),
  activeTool: z.unknown().nullable(),
  createdAt: z.string(),
  workspaceId: z.string().min(1).optional(),
  updatedAt: z.string().optional(),
  elapsedMs: z.number().optional(),
  finishedAt: z.string().optional(),
  durationMs: z.number().optional(),
  costUsd: z.number().optional(),
  estimatedCostUsd: z.number().nullable().optional(),
});

export type RunSummary = z.infer<typeof RunSummarySchema>;

export const CreateRunSchema = z.object({
  agentPreset: z.string(),
  workspaceId: z.string(),
});

export const RunDetailUIStateSchema = z.object({
  selectedTab: z.enum(['overview', 'events', 'plan', 'terminal', 'browser', 'artifacts', 'diff', 'trace']),
  selectedEventId: z.union([z.string(), z.number(), z.null()]),
  diffMode: z.enum(['split', 'unified']),
  inspectorOpen: z.boolean(),
  latestStreamEventId: z.number(),
});
