import { z } from 'zod';

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'remote-api']);
export const WorkspaceHealthSchema = z.enum(['healthy', 'warning', 'error', 'disconnected']);
export const WorkspaceIsolationModeSchema = z.enum(['shared', 'isolated', 'strict']);

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(80),
  type: WorkspaceTypeSchema,
  health: WorkspaceHealthSchema,
  agentServerUrl: z.string().url().optional(),
  isolationMode: WorkspaceIsolationModeSchema.default('isolated'),
  runCount: z.number().int().nonnegative().default(0),
  activeRunId: z.string().nullable().default(null),
  lastSeenAt: z.string().datetime({ offset: true }).nullable().default(null),
  createdAt: z.string().datetime({ offset: true }),
  updatedAt: z.string().datetime({ offset: true }),
  meta: z.record(z.unknown()).optional(),
});

export const WorkspaceListSchema = z.array(WorkspaceSchema);

export const CreateWorkspaceRequestSchema = z.object({
  name: z.string().min(1).max(80),
  type: WorkspaceTypeSchema,
  agentServerUrl: z.string().url().optional(),
  isolationMode: WorkspaceIsolationModeSchema.optional(),
});

export const ResetWorkspaceResponseSchema = z.object({
  workspaceId: z.string(),
  status: z.literal('reset'),
  resetAt: z.string().datetime({ offset: true }),
});

export type Workspace = z.infer<typeof WorkspaceSchema>;
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;
export type WorkspaceHealth = z.infer<typeof WorkspaceHealthSchema>;
export type CreateWorkspaceRequest = z.infer<typeof CreateWorkspaceRequestSchema>;
export type ResetWorkspaceResponse = z.infer<typeof ResetWorkspaceResponseSchema>;
