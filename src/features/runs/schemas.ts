import { z } from 'zod';
import { RunSummarySchema, RunStatusSchema } from '@/lib/schemas/run';

export { RunSummarySchema, RunStatusSchema };

export const CreateRunRequestSchema = z.object({
  title: z.string().min(1, 'Task description is required'),
  agentPresetId: z.string().min(1),
  workspaceId: z.string().min(1),
  contextPrompt: z.string().optional(),
});

export type CreateRunRequest = z.infer<typeof CreateRunRequestSchema>;

export const AgentPresetSchema = z.object({
  id: z.string(),
  name: z.string(),
  model: z.string(),
  description: z.string().optional(),
});

export type AgentPreset = z.infer<typeof AgentPresetSchema>;

export const RunsFilterSchema = z.object({
  status: RunStatusSchema.optional(),
  workspaceType: z.enum(['local', 'docker', 'remote_api']).optional(),
  search: z.string().optional(),
});

export type RunsFilter = z.infer<typeof RunsFilterSchema>;
