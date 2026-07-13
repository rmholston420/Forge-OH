export {
  WorkspaceTypeSchema,
  type WorkspaceType,
  WorkspaceStatusSchema,
  type WorkspaceStatus,
  WorkspaceHealthSchema,
  type WorkspaceHealth,
  EnvVarSchema,
  type EnvVar,
  WorkspaceSchema,
  type Workspace,
  CreateWorkspaceSchema,
  type CreateWorkspace,
  UpdateWorkspaceSchema,
  type UpdateWorkspace,
} from '@/lib/schemas/workspace';

export type {
  CreateWorkspace as CreateWorkspaceRequest,
  UpdateWorkspace as UpdateWorkspaceRequest,
} from '@/lib/schemas/workspace';
