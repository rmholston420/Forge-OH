'use client';
import { useQuery } from '@tanstack/react-query';
import {
  fetchRunFiles,
  fetchFileDiff,
  fetchGitChanges,
  fetchGitDiff,
  type GitChangeRow,
  type GitDiffSides,
} from './api';
import type { FileDiff, FileDiffSummary } from '@/lib/schemas/file-diff';

export function useRunFiles(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'files'],
    queryFn: () => fetchRunFiles(runId),
    enabled: !!runId,
  });
}

export function useFileDiff(runId: string, path: string | null) {
  return useQuery({
    queryKey: ['runs', runId, 'files', path],
    queryFn: () => fetchFileDiff(runId, path!),
    enabled: !!runId && !!path,
  });
}

// ---------------------------------------------------------------------------
// Real git diff (Slice C.2)
// ---------------------------------------------------------------------------

type GitStatus = FileDiffSummary['status'];

function normalizeGitStatus(raw: string): GitStatus {
  const s = (raw || '').toLowerCase();
  if (s.startsWith('a')) return 'added';
  if (s.startsWith('m')) return 'modified';
  if (s.startsWith('d')) return 'deleted';
  if (s.startsWith('r')) return 'renamed';
  return 'untracked';
}

function detectLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', rb: 'ruby', go: 'go', rs: 'rust', java: 'java',
    c: 'c', cc: 'cpp', cpp: 'cpp', h: 'c', hpp: 'cpp',
    md: 'markdown', json: 'json', yaml: 'yaml', yml: 'yaml',
    css: 'css', scss: 'scss', html: 'html', sh: 'bash', bash: 'bash',
    sql: 'sql', toml: 'toml',
  };
  return (ext && map[ext]) || 'plaintext';
}

function countLineDelta(original: string | null, modified: string | null): {
  additions: number;
  deletions: number;
} {
  // Cheap line-count delta — good enough for the sidebar badge without
  // needing a full diff library. Real per-hunk diff still happens in
  // DiffViewer via its existing renderer.
  const oLines = original ? original.split('\n').length : 0;
  const mLines = modified ? modified.split('\n').length : 0;
  return {
    additions: Math.max(0, mLines - oLines),
    deletions: Math.max(0, oLines - mLines),
  };
}

/**
 * Convert an upstream (status, path) pair into the FileDiffSummary shape
 * the existing FileList expects. The additions/deletions are unknown at
 * this point (we haven't fetched the file's diff yet) so we mark them 0.
 */
function changeToSummary(row: GitChangeRow): FileDiffSummary {
  return {
    path: row.path,
    status: normalizeGitStatus(row.status),
    additions: 0,
    deletions: 0,
    language: detectLanguage(row.path),
    isBinary: false,
  };
}

/**
 * Convert a `{original, modified}` pair from upstream into the FileDiff
 * shape DiffViewer already renders.
 */
function sidesToDiff(sides: GitDiffSides, status: GitStatus): FileDiff {
  const { additions, deletions } = countLineDelta(sides.original, sides.modified);
  return {
    path: sides.path,
    status,
    additions,
    deletions,
    original: sides.original,
    modified: sides.modified,
    language: detectLanguage(sides.path),
    isBinary: false,
  };
}

export function useGitChanges(runId: string, workspacePath: string | null | undefined) {
  return useQuery({
    queryKey: ['runs', runId, 'git', 'changes', workspacePath ?? ''],
    queryFn: async () => {
      const rows = await fetchGitChanges(runId, workspacePath as string);
      return rows.map(changeToSummary);
    },
    enabled: !!runId && !!workspacePath,
  });
}

export function useGitDiff(
  runId: string,
  filePath: string | null,
  workspacePath: string | null | undefined,
  status: GitStatus = 'modified',
) {
  return useQuery({
    queryKey: ['runs', runId, 'git', 'diff', filePath, workspacePath ?? ''],
    queryFn: async () => {
      const sides = await fetchGitDiff(runId, filePath as string, workspacePath ?? null);
      return sidesToDiff(sides, status);
    },
    enabled: !!runId && !!filePath,
  });
}
