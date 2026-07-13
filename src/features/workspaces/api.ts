import type { Workspace } from '@/lib/schemas/workspace';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchWorkspaces(): Promise<Workspace[]> {
  const res = await fetch(`${BFF}/api/workspaces`);
  if (!res.ok) throw new Error(`Failed to fetch workspaces: ${res.status}`);
  const json = await res.json();
  return json.data;
}
