import type { BrowserFrame } from '@/lib/schemas/browser';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchBrowserFrames(runId: string): Promise<BrowserFrame[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/browser`);
  if (!res.ok) throw new Error(`fetchBrowserFrames failed: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}
