import type { Secret, CreateSecretRequest } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchSecrets(scope?: string): Promise<Secret[]> {
  const url = scope ? `${BASE}/secrets?scope=${scope}` : `${BASE}/secrets`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch secrets');
  return res.json();
}

export async function createSecret(body: CreateSecretRequest): Promise<Secret> {
  const res = await fetch(`${BASE}/secrets`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create secret');
  return res.json();
}

export async function rotateSecret(id: string, newValue: string): Promise<Secret> {
  const res = await fetch(`${BASE}/secrets/${id}/rotate`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ newValue }),
  });
  if (!res.ok) throw new Error('Failed to rotate secret');
  return res.json();
}

export async function deleteSecret(id: string): Promise<void> {
  const res = await fetch(`${BASE}/secrets/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete secret');
}
