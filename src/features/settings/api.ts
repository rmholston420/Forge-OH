import type { Settings, UpdateSettingsRequest } from '@/lib/schemas/settings';

const BASE = `${process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081'}/api/settings`;

export async function fetchSettings(): Promise<Settings> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateSettings(patch: UpdateSettingsRequest): Promise<Settings> {
  const res = await fetch(BASE, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

export async function resetSettings(): Promise<Settings> {
  const res = await fetch(`${BASE}/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset settings');
  return res.json();
}
