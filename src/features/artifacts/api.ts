import type { Artifact } from '@/lib/schemas/artifact';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRunArtifacts(runId: string): Promise<Artifact[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/artifacts`);
  if (!res.ok) throw new Error(`Failed to fetch artifacts: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}
