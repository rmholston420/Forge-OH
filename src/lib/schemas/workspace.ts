import { z } from 'zod';

export const WorkspaceHealthSchema = z.enum(['healthy', 'warning', 'error', 'disconnected']);
export type WorkspaceHealth = z.infer<typeof WorkspaceHealthSchema>;

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(['local', 'docker', 'remote_api']),
  health: WorkspaceHealthSchema,
  agentServerUrl: z.string().optional(),
  isolationMode: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type Workspace = z.infer<typeof WorkspaceSchema>;
