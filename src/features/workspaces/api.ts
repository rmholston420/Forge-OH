import { apiClient } from '@/lib/api/client';
import type { Workspace, CreateWorkspaceRequest, ResetWorkspaceResponse } from './schemas';
import { WorkspaceListSchema, WorkspaceSchema, ResetWorkspaceResponseSchema } from './schemas';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const data = await apiClient.get('/workspaces');
  return WorkspaceListSchema.parse(data);
}

export async function fetchWorkspace(id: string): Promise<Workspace> {
  const data = await apiClient.get(`/workspaces/${id}`);
  return WorkspaceSchema.parse(data);
}

export async function createWorkspace(payload: CreateWorkspaceRequest): Promise<Workspace> {
  const data = await apiClient.post('/workspaces', payload);
  return WorkspaceSchema.parse(data);
}

export async function resetWorkspace(id: string): Promise<ResetWorkspaceResponse> {
  const data = await apiClient.post(`/workspaces/${id}/reset`, {});
  return ResetWorkspaceResponseSchema.parse(data);
}

export async function duplicateWorkspace(id: string, name: string): Promise<Workspace> {
  const data = await apiClient.post(`/workspaces/${id}/duplicate`, { name });
  return WorkspaceSchema.parse(data);
}

export async function deleteWorkspace(id: string): Promise<void> {
  await apiClient.delete(`/workspaces/${id}`);
}
