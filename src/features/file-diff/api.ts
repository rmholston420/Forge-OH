import type { FileDiff, FileDiffSummary } from '@/lib/schemas/file-diff';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

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

// -------------------------------------------------------------------------
// Real git diff (Slice C.2)
// -------------------------------------------------------------------------

export interface GitChangeRow {
  status: string;
  path: string;
}

export interface GitDiffSides {
  path: string;
  original: string | null;
  modified: string | null;
}

export async function fetchGitChanges(
  runId: string,
  workspacePath: string,
): Promise<GitChangeRow[]> {
  const url = new URL(`${BFF}/api/runs/${runId}/git/changes`);
  url.searchParams.set('workspace_path', workspacePath);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch git changes: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

export async function fetchGitDiff(
  runId: string,
  filePath: string,
  workspacePath?: string | null,
): Promise<GitDiffSides> {
  const url = new URL(`${BFF}/api/runs/${runId}/git/diff`);
  url.searchParams.set('file_path', filePath);
  if (workspacePath) url.searchParams.set('workspace_path', workspacePath);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`Failed to fetch git diff: ${res.status}`);
  const json = await res.json();
  return json.data;
}
