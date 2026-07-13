import type { Workspace, CreateWorkspaceRequest, UpdateWorkspaceRequest } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const res = await fetch(`${BASE}/api/workspaces`);
  if (!res.ok) throw new Error('Failed to fetch workspaces');
  return res.json();
}

export async function fetchWorkspace(id: string): Promise<Workspace> {
  const res = await fetch(`${BASE}/api/workspaces/${id}`);
  if (!res.ok) throw new Error('Failed to fetch workspace');
  return res.json();
}

export async function createWorkspace(body: CreateWorkspaceRequest): Promise<Workspace> {
  const res = await fetch(`${BASE}/api/workspaces`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create workspace');
  return res.json();
}

export async function updateWorkspace(id: string, body: UpdateWorkspaceRequest): Promise<Workspace> {
  const res = await fetch(`${BASE}/api/workspaces/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update workspace');
  return res.json();
}

export async function deleteWorkspace(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/workspaces/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete workspace');
}

export async function resetWorkspace(id: string): Promise<Workspace> {
  const res = await fetch(`${BASE}/api/workspaces/${id}/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset workspace');
  return res.json();
}
