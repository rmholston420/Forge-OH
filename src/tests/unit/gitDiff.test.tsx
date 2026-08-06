/**
 * Slice C.2 unit tests for the git-diff hook conversion + FilesTab toggle.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { useGitChanges, useGitDiff } from '@/features/file-diff/hooks';
import { FilesTab } from '@/app/(dashboard)/runs/[runId]/tabs/FilesTab';
import { renderHook } from '@testing-library/react';
import React from 'react';

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('useGitChanges', () => {
  it('maps upstream rows to FileDiffSummary shape', async () => {
    server.use(
      http.get('http://localhost:8081/api/runs/r1/git/changes', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('workspace_path')).toBe('/workspace/runs/pending');
        return HttpResponse.json({
          data: [
            { status: 'modified', path: 'src/a.py' },
            { status: 'added', path: 'src/b.ts' },
            { status: 'deleted', path: 'src/c.md' },
          ],
        });
      }),
    );

    const { result } = renderHook(
      () => useGitChanges('r1', '/workspace/runs/pending'),
      { wrapper: wrap() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const rows = result.current.data!;
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatchObject({
      path: 'src/a.py',
      status: 'modified',
      language: 'python',
      isBinary: false,
    });
    expect(rows[1].language).toBe('typescript');
    expect(rows[2].status).toBe('deleted');
  });

  it('is disabled when workspacePath is null', () => {
    const { result } = renderHook(() => useGitChanges('r1', null), {
      wrapper: wrap(),
    });
    expect(result.current.fetchStatus).toBe('idle');
  });
});

describe('useGitDiff', () => {
  it('joins workspace + file into a FileDiff and computes line delta', async () => {
    server.use(
      http.get('http://localhost:8081/api/runs/r1/git/diff', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('file_path')).toBe('src/a.py');
        expect(url.searchParams.get('workspace_path')).toBe('/ws');
        return HttpResponse.json({
          data: {
            path: 'src/a.py',
            original: 'x\ny\n',
            modified: 'x\ny\nz\n',
          },
        });
      }),
    );
    const { result } = renderHook(
      () => useGitDiff('r1', 'src/a.py', '/ws', 'modified'),
      { wrapper: wrap() },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const d = result.current.data!;
    expect(d.status).toBe('modified');
    expect(d.language).toBe('python');
    expect(d.additions).toBe(1);
    expect(d.deletions).toBe(0);
    expect(d.modified).toContain('z');
  });
});

describe('FilesTab — Real git diff toggle', () => {
  it('renders the toggle when run has a local workspace path', async () => {
    server.use(
      http.get('http://localhost:8081/api/runs/r1', () =>
        HttpResponse.json({
          data: {
            id: 'r1',
            title: 'Run r1',
            status: 'queued',
            // Fields required by RunSummarySchema (src/lib/schemas/run.ts).
            // Added by Stage 7-C.2-hotfix (2026-08-06) — Stage-3 hygiene
            // tightened the schema after slice C.2 landed, and the fixture
            // never caught up. Without these the RunSummarySchema.parse
            // tripwire in fetchRun throws → useRunDetail errors →
            // workspacePath is null → the diff-source-toggle never renders.
            agentPresetName: 'ap-1',
            activeTool: null,
            elapsedMs: null,
            estimatedCostUsd: null,
            workspaceId: '/workspace/runs/pending',
            workspaceType: 'local',
            createdAt: '2026-08-03T10:00:00Z',
            updatedAt: '2026-08-03T10:00:00Z',
          },
        }),
      ),
      http.get('http://localhost:8081/api/runs/r1/files', () =>
        HttpResponse.json({ data: [] }),
      ),
      http.get('http://localhost:8081/api/runs/r1/git/changes', () =>
        HttpResponse.json({
          data: [{ status: 'modified', path: 'src/a.py' }],
        }),
      ),
    );

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <FilesTab runId="r1" />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId('diff-source-toggle')).toBeInTheDocument(),
    );
    // Default is reconstructed source (Real git diff button not pressed).
    const gitBtn = screen.getByTestId('diff-source-git');
    expect(gitBtn).toHaveAttribute('aria-pressed', 'false');

    // Flip to Real git diff → the row from upstream shows up.
    fireEvent.click(gitBtn);
    await waitFor(() => expect(screen.getByText('src/a.py')).toBeInTheDocument());
    expect(gitBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('hides the toggle when the workspace has no absolute path', async () => {
    server.use(
      http.get('http://localhost:8081/api/runs/r2', () =>
        HttpResponse.json({
          data: {
            id: 'r2',
            title: 'Run r2',
            status: 'queued',
            // See r1 fixture above for the Stage 7-C.2-hotfix rationale.
            agentPresetName: 'ap-1',
            activeTool: null,
            elapsedMs: null,
            estimatedCostUsd: null,
            workspaceId: 'local',
            workspaceType: 'local',
            createdAt: '2026-08-03T10:00:00Z',
            updatedAt: '2026-08-03T10:00:00Z',
          },
        }),
      ),
      http.get('http://localhost:8081/api/runs/r2/files', () =>
        HttpResponse.json({ data: [] }),
      ),
    );

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <FilesTab runId="r2" />
      </QueryClientProvider>,
    );

    // Give the query time to resolve then confirm the toggle is absent.
    await waitFor(() =>
      expect(screen.getByText('No files changed')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('diff-source-toggle')).not.toBeInTheDocument();
  });
});
