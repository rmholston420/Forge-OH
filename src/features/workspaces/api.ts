import type { Workspace, CreateWorkspace } from '@/lib/schemas/workspace';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const res = await fetch(`${BFF}/api/workspaces`);
  if (!res.ok) throw new Error(`Failed to fetch workspaces: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

export async function fetchWorkspace(id: string): Promise<Workspace> {
  const res = await fetch(`${BFF}/api/workspaces/${id}`);
  if (!res.ok) throw new Error(`Failed to fetch workspace: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function createWorkspace(body: CreateWorkspace): Promise<Workspace> {
  const res = await fetch(`${BFF}/api/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to create workspace: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function updateWorkspace(id: string, body: Partial<CreateWorkspace>): Promise<Workspace> {
  const res = await fetch(`${BFF}/api/workspaces/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to update workspace: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function deleteWorkspace(id: string): Promise<void> {
  const res = await fetch(`${BFF}/api/workspaces/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete workspace: ${res.status}`);
}

export async function testWorkspaceConnection(id: string): Promise<{ ok: boolean; latencyMs: number | null; error: string | null }> {
  const res = await fetch(`${BFF}/api/workspaces/${id}/test`, { method: 'POST' });
  if (!res.ok) throw new Error(`Connection test failed: ${res.status}`);
  return res.json();
}
