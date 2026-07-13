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
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;

export const RunSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  status: RunStatusSchema,
  agentPresetName: z.string(),
  workspaceId: z.string(),
  workspaceType: WorkspaceTypeSchema,
  activeTool: z.string().nullable(),
  updatedAt: z.string(),
  createdAt: z.string(),
  elapsedMs: z.number().nullable(),
  estimatedCostUsd: z.number().nullable(),
});

export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunDetailUIStateSchema = z.object({
  selectedTab: z.enum(['overview', 'files', 'terminal', 'browser', 'metrics', 'security']),
  selectedEventId: z.string().nullable(),
  diffMode: z.enum(['split', 'unified']),
  inspectorOpen: z.boolean(),
  latestStreamEventId: z.number(),
  pendingApprovalBanner: z.boolean(),
});

export type RunDetailUIState = z.infer<typeof RunDetailUIStateSchema>;
