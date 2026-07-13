import type { Plugin, InstallPlugin } from '@/lib/schemas/plugin';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchPlugins(): Promise<Plugin[]> {
  const res = await fetch(`${BFF}/api/plugins`);
  if (!res.ok) throw new Error(`Failed to fetch plugins: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

export async function installPlugin(body: InstallPlugin): Promise<Plugin> {
  const res = await fetch(`${BFF}/api/plugins`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to install plugin: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function togglePlugin(id: string, enabled: boolean): Promise<Plugin> {
  const res = await fetch(`${BFF}/api/plugins/${id}/${enabled ? 'enable' : 'disable'}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to toggle plugin: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function uninstallPlugin(id: string): Promise<void> {
  const res = await fetch(`${BFF}/api/plugins/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to uninstall plugin: ${res.status}`);
}

export async function pingPlugin(id: string): Promise<{ ok: boolean; latencyMs: number | null }> {
  const res = await fetch(`${BFF}/api/plugins/${id}/ping`, { method: 'POST' });
  if (!res.ok) throw new Error(`Plugin ping failed: ${res.status}`);
  return res.json();
}
