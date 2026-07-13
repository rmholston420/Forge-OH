import { z } from 'zod';

export const WorkspaceTypeSchema = z.enum(['local', 'docker', 'e2b', 'modal']);
export type WorkspaceType = z.infer<typeof WorkspaceTypeSchema>;

export const WorkspaceStatusSchema = z.enum(['idle', 'active', 'error', 'provisioning']);
export type WorkspaceStatus = z.infer<typeof WorkspaceStatusSchema>;

export const EnvVarSchema = z.object({
  key:    z.string().min(1, 'Key required'),
  value:  z.string(),
  masked: z.boolean().default(true),
});
export type EnvVar = z.infer<typeof EnvVarSchema>;

export const WorkspaceSchema = z.object({
  id:            z.string(),
  name:          z.string().min(1).max(64),
  description:   z.string().max(256).optional(),
  type:          WorkspaceTypeSchema,
  status:        WorkspaceStatusSchema,
  createdAt:     z.string().datetime(),
  updatedAt:     z.string().datetime(),
  runCount:      z.number().int().min(0),
  diskUsageMb:   z.number().min(0),
  diskLimitMb:   z.number().min(0).default(2048),
  envVars:       z.array(EnvVarSchema).default([]),
  agentPresetId: z.string().optional(),
});
export type Workspace = z.infer<typeof WorkspaceSchema>;

export const CreateWorkspaceSchema = WorkspaceSchema.pick({
  name: true, description: true, type: true, agentPresetId: true,
}).extend({ envVars: z.array(EnvVarSchema).default([]) });
export type CreateWorkspaceRequest = z.infer<typeof CreateWorkspaceSchema>;

export const UpdateWorkspaceSchema = CreateWorkspaceSchema.partial();
export type UpdateWorkspaceRequest = z.infer<typeof UpdateWorkspaceSchema>;
