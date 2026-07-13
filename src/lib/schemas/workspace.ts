import { z } from 'zod';

export const WorkspaceHealthSchema = z.enum(['healthy', 'warning', 'error', 'disconnected']);

export const WorkspaceSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.enum(['local', 'docker', 'remote_api']),
  health: WorkspaceHealthSchema,
  agentServerUrl: z.string().url().optional(),
  isolationMode: z.enum(['none', 'container', 'vm']).optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  meta: z.record(z.unknown()).optional(),
});

export type Workspace = z.infer<typeof WorkspaceSchema>;

export const WorkspaceListSchema = z.array(WorkspaceSchema);
export type WorkspaceList = z.infer<typeof WorkspaceListSchema>;
