import { z } from 'zod';

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'remote_api', 'remoteapi', 'e2b', 'modal']);
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;

export const WorkspaceStatusSchema = z.enum(['idle', 'active', 'inactive', 'error', 'provisioning']);
export type WorkspaceStatus = z.infer<typeof WorkspaceStatusSchema>;

export const WorkspaceHealthSchema = z.enum(['healthy', 'warning', 'error', 'disconnected']);
export type WorkspaceHealth = z.infer<typeof WorkspaceHealthSchema>;

export const EnvVarSchema = z.object({
  key: z.string().default(''),
  value: z.string().default(''),
  masked: z.boolean().default(true),
});
export type EnvVar = z.infer<typeof EnvVarSchema>;

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: WorkspaceTypeSchema.default('local'),
  status: WorkspaceStatusSchema.default('idle'),
  health: WorkspaceHealthSchema.default('healthy'),
  description: z.string().optional(),
  repoUrl: z.string().optional(),
  endpoint: z.string().optional(),
  path: z.string().optional(),
  lastUsedAt: z.string().optional(),
  baseDir: z.string().optional(),
  dockerImage: z.string().optional(),
  remoteUrl: z.string().optional(),
  agentServerUrl: z.string().optional(),
  isolationMode: z.string().optional(),
  runCount: z.number().default(0),
  activeRunCount: z.number().default(0),
  activeRunId: z.string().optional(),
  diskUsageMb: z.number().default(0),
  diskLimitMb: z.number().default(0),
  envVars: z.array(EnvVarSchema).default([]),
  agentPresetId: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string().optional(),
  lastSeenAt: z.string().optional(),
});
export type Workspace = Partial<z.infer<typeof WorkspaceSchema>> & Pick<z.infer<typeof WorkspaceSchema>, 'id' | 'name'>;

export const CreateWorkspaceSchema = z.object({
  name: z.string().min(1).default(''),
  description: z.string().optional(),
  type: WorkspaceTypeSchema.default('local'),
  agentPresetId: z.string().optional(),
  baseDir: z.string().optional(),
  dockerImage: z.string().optional(),
  remoteUrl: z.string().optional(),
  envVars: z.array(EnvVarSchema).default([]),
});
export type CreateWorkspace = z.infer<typeof CreateWorkspaceSchema>;

export const UpdateWorkspaceSchema = CreateWorkspaceSchema.partial().extend({
  id: z.string().optional(),
});
export type UpdateWorkspace = z.infer<typeof UpdateWorkspaceSchema>;
