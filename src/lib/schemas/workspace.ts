import { z } from 'zod';

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'remote_api']);
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;

export const WorkspaceHealthSchema = z.enum(['healthy', 'degraded', 'offline', 'unknown']);
export type WorkspaceHealth = z.infer<typeof WorkspaceHealthSchema>;

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: WorkspaceTypeSchema,
  health: WorkspaceHealthSchema,
  description: z.string().optional(),
  dockerImage: z.string().optional(),
  remoteUrl: z.string().url().optional(),
  localPath: z.string().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  isDefault: z.boolean().optional(),
});

export type Workspace = z.infer<typeof WorkspaceSchema>;


export const WorkspaceEnvVarSchema = z.object({
  key: z.string().min(1, 'Key is required'),
  value: z.string(),
});

export type WorkspaceEnvVar = z.infer<typeof WorkspaceEnvVarSchema>;

export const CreateWorkspaceSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  type: WorkspaceTypeSchema,
  description: z.string().optional(),
  baseDir: z.string().optional(),
  dockerImage: z.string().optional(),
  remoteUrl: z.union([z.literal(''), z.string().url('Remote URL must be a valid URL')]).optional(),
  envVars: z.array(WorkspaceEnvVarSchema).default([]),
}).superRefine((data, ctx) => {
  if (data.type === 'local' && !data.baseDir?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['baseDir'],
      message: 'Base Directory is required for local workspaces',
    })
  }

  if (data.type === 'docker' && !data.dockerImage?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['dockerImage'],
      message: 'Docker Image is required for docker workspaces',
    })
  }

  if (data.type === 'remote_api' && !data.remoteUrl?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['remoteUrl'],
      message: 'Remote URL is required for remote API workspaces',
    })
  }
});

export type CreateWorkspace = z.infer<typeof CreateWorkspaceSchema>;


export const WorkspaceListResponseSchema = z.object({
  workspaces: z.array(WorkspaceSchema),
  total: z.number(),
});

export type WorkspaceListResponse = z.infer<typeof WorkspaceListResponseSchema>;
