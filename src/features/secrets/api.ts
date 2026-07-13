import type { Secret, UpsertSecret } from '@/lib/schemas/secret';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchSecrets(): Promise<Secret[]> {
  const res = await fetch(`${BFF}/api/secrets`);
  if (!res.ok) throw new Error(`Failed to fetch secrets: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

export async function upsertSecret(body: UpsertSecret): Promise<Secret> {
  const res = await fetch(`${BFF}/api/secrets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Failed to save secret: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function deleteSecret(id: string): Promise<void> {
  const res = await fetch(`${BFF}/api/secrets/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Failed to delete secret: ${res.status}`);
}

export async function rotateSecret(id: string, newValue: string): Promise<Secret> {
  const res = await fetch(`${BFF}/api/secrets/${id}/rotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: newValue }),
  });
  if (!res.ok) throw new Error(`Failed to rotate secret: ${res.status}`);
  const json = await res.json();
  return json.data;
}
