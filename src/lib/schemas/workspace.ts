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

export const WorkspaceListResponseSchema = z.object({
  workspaces: z.array(WorkspaceSchema),
  total: z.number(),
});

export type WorkspaceListResponse = z.infer<typeof WorkspaceListResponseSchema>;
