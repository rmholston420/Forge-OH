import type { FileDiff, FileDiffSummary } from '@/lib/schemas/file-diff';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRunFiles(runId: string): Promise<FileDiffSummary[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/files`);
  if (!res.ok) throw new Error(`Failed to fetch files: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

export async function fetchFileDiff(runId: string, path: string): Promise<FileDiff> {
  const encoded = encodeURIComponent(path);
  const res = await fetch(`${BFF}/api/runs/${runId}/files/${encoded}`);
  if (!res.ok) throw new Error(`Failed to fetch diff: ${res.status}`);
  const json = await res.json();
  return json.data;
}
