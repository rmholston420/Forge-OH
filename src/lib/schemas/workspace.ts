import { z } from 'zod';

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'remote_api']);

export const WorkspaceStatusSchema = z.enum(['active', 'inactive', 'error', 'provisioning']);

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(80),
  type: WorkspaceTypeSchema,
  status: WorkspaceStatusSchema,
  description: z.string().nullable().default(null),
  baseDir: z.string().nullable().default(null),
  dockerImage: z.string().nullable().default(null),
  remoteUrl: z.string().url().nullable().default(null),
  envVars: z.record(z.string()).default({}),
  createdAt: z.string(),
  updatedAt: z.string(),
  lastUsedAt: z.string().nullable().default(null),
  activeRunCount: z.number().int().min(0).default(0),
});

export const CreateWorkspaceSchema = WorkspaceSchema.pick({
  name: true,
  type: true,
  description: true,
  baseDir: true,
  dockerImage: true,
  remoteUrl: true,
  envVars: true,
});

export type Workspace = z.infer<typeof WorkspaceSchema>;
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;
export type WorkspaceStatus = z.infer<typeof WorkspaceStatusSchema>;
export type CreateWorkspace = z.infer<typeof CreateWorkspaceSchema>;
