/**
 * src/features/workspaces/api.ts
 *
 * All BFF calls for the Workspaces feature.
 * Uses bffGet/bffPost/bffPatch/bffDelete from lib/api/client + ENDPOINTS.
 */
import { bffGet, bffPost, bffPatch, bffDelete } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import type { Workspace, CreateWorkspaceRequest, UpdateWorkspaceRequest } from './schemas';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const res = await bffGet<Workspace[] | { data: Workspace[] }>(ENDPOINTS.WORKSPACES.list());
  const data = unwrap(res);
  return Array.isArray(data) ? data : (data as { data: Workspace[] }).data;
}

export async function fetchWorkspace(id: string): Promise<Workspace> {
  const res = await bffGet<Workspace>(ENDPOINTS.WORKSPACES.get(id));
  return unwrap(res);
}

export async function createWorkspace(body: CreateWorkspaceRequest): Promise<Workspace> {
  const res = await bffPost<Workspace>(ENDPOINTS.WORKSPACES.create(), body);
  return unwrap(res);
}

export async function updateWorkspace(id: string, body: UpdateWorkspaceRequest): Promise<Workspace> {
  const res = await bffPatch<Workspace>(ENDPOINTS.WORKSPACES.update(id), body);
  return unwrap(res);
}

export async function deleteWorkspace(id: string): Promise<void> {
  await bffDelete<{ ok: boolean }>(ENDPOINTS.WORKSPACES.delete(id));
}

// Real BFF endpoint: POST /api/workspaces/{id}/test — verifies path exists,
// is a directory, and is read/writable by the BFF process. Returns
// TestConnectionResult { ok, error?, latencyMs? }.
export type TestConnectionResult = {
  ok: boolean;
  error?: string;
  latencyMs?: number;
};

export async function testWorkspace(id: string): Promise<TestConnectionResult> {
  const res = await bffPost<TestConnectionResult>(ENDPOINTS.WORKSPACES.test(id), {});
  return unwrap(res);
}
