import { z } from 'zod';

/**
 * Stage 6: workspaces are backed by openhands agent-server's registry.
 * WorkspaceItem shape is minimal: {id, name, path, parentPath?}.
 * We keep a `type: 'local'` literal so downstream code that reads .type
 * doesn't need to change, and expose a few optional legacy fields the
 * WorkspaceCard renders (health/status/runCount/diskUsage) with safe
 * defaults so cards degrade gracefully.
 */

export const WorkspaceTypeSchema = z.literal('local');
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;

export const WorkspaceHealthSchema = z.enum(['healthy', 'degraded', 'offline', 'unknown']);
export type WorkspaceHealth = z.infer<typeof WorkspaceHealthSchema>;

export const WorkspaceStatusSchema = z.enum(['idle', 'active', 'inactive', 'error', 'provisioning']);
export type WorkspaceStatus = z.infer<typeof WorkspaceStatusSchema>;

export const WorkspaceEnvVarSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string(),
});
export type WorkspaceEnvVar = z.infer<typeof WorkspaceEnvVarSchema>;
// Backwards-compat alias used by src/features/workspaces/schemas.ts re-exports
export const EnvVarSchema = WorkspaceEnvVarSchema;
export type EnvVar = WorkspaceEnvVar;

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: WorkspaceTypeSchema.default('local'),
  path: z.string(),
  parentPath: z.string().nullable().optional(),
  // Optional legacy fields — BFF sends safe defaults for these.
  description: z.string().optional(),
  health: WorkspaceHealthSchema.optional(),
  status: WorkspaceStatusSchema.optional(),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
  runCount: z.number().optional(),
  activeRunCount: z.number().optional(),
  diskUsageMb: z.number().optional(),
  diskLimitMb: z.number().optional(),
  envVars: z.array(WorkspaceEnvVarSchema).optional(),
  agentPresetId: z.string().nullable().optional(),
});
export type Workspace = z.infer<typeof WorkspaceSchema>;

export const CreateWorkspaceSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  path: z.string().optional(),
  parentPath: z.string().nullable().optional(),
  description: z.string().optional(),
  // Kept so existing form code that spreads a `type` field still validates.
  type: WorkspaceTypeSchema.default('local'),
  envVars: z.array(WorkspaceEnvVarSchema).default([]),
});
export type CreateWorkspace = z.infer<typeof CreateWorkspaceSchema>;

export const UpdateWorkspaceSchema = z.object({
  name: z.string().min(1).optional(),
  path: z.string().optional(),
  parentPath: z.string().nullable().optional(),
});
export type UpdateWorkspace = z.infer<typeof UpdateWorkspaceSchema>;

export const WorkspaceListResponseSchema = z.object({
  workspaces: z.array(WorkspaceSchema),
  total: z.number(),
});
export type WorkspaceListResponse = z.infer<typeof WorkspaceListResponseSchema>;
