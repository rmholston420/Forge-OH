import type { Trace } from '@/lib/schemas/trace';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchTrace(runId: string): Promise<Trace | null> {
  const res = await fetch(`${BFF}/api/runs/${runId}/trace`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`fetchTrace failed: ${res.status}`);
  const json = await res.json();
  return json.data;
}
