import type { RunMetrics } from '@/lib/schemas/metric';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRunMetrics(runId: string): Promise<RunMetrics> {
  const res = await fetch(`${BFF}/api/runs/${runId}/metrics`);
  if (!res.ok) throw new Error(`fetchRunMetrics failed: ${res.status}`);
  const json = await res.json();
  return json.data;
}
