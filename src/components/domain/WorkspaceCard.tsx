'use client';
import React from 'react';
import { Badge } from '@/components/core/Badge';
import type { Workspace } from '@/lib/schemas/workspace';
import {
  useDeleteWorkspace,
  useTestWorkspaceConnection,
} from '@/features/workspaces/hooks';
import { useWorkspacesStore } from '@/features/workspaces/store';

/**
 * Stage 6: workspaces are local-only. The card shows name + path and
 * exposes edit / test / delete row actions.
 */

const statusColors: Record<'idle' | 'active' | 'inactive' | 'error' | 'provisioning', string> = {
  idle: 'muted',
  active: 'success',
  inactive: 'muted',
  error: 'danger',
  provisioning: 'warning',
};

type Props = {
  workspace: Workspace;
};

export function WorkspaceCard({ workspace }: Props) {
  const status = workspace.status ?? 'idle';
  const testMut = useTestWorkspaceConnection();
  const deleteMut = useDeleteWorkspace();
  const { openEditDrawer } = useWorkspacesStore();

  const testResult = testMut.data as { ok?: boolean; error?: string; latencyMs?: number } | undefined;

  const handleTest = () => {
    testMut.reset();
    testMut.mutate(workspace.id);
  };

  const handleDelete = () => {
    if (confirm(`Delete workspace "${workspace.name}"? This cannot be undone.`)) {
      deleteMut.mutate(workspace.id);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{workspace.name}</h3>
          <p className="text-xs text-[var(--color-text-muted)]">Local · filesystem</p>
        </div>
        <Badge variant={statusColors[status] as never}>{status}</Badge>
      </div>

      <div className="mt-3 flex flex-col gap-1 text-xs text-[var(--color-text-muted)]">
        <span title={workspace.path} className="truncate font-mono">{workspace.path}</span>
      </div>

      {testMut.isPending && (
        <div className="mt-3 text-xs text-[var(--color-text-muted)]">Testing connection…</div>
      )}
      {!testMut.isPending && testResult?.ok === true && (
        <div className="mt-3 text-xs" style={{ color: 'var(--color-success, #10b981)' }}>
          ✓ Reachable{typeof testResult.latencyMs === 'number' ? ` · ${testResult.latencyMs.toFixed(0)}ms` : ''}
        </div>
      )}
      {!testMut.isPending && testResult?.ok === false && (
        <div className="mt-3 text-xs" style={{ color: 'var(--color-danger, #ef4444)' }}>
          ✕ {testResult.error ?? 'Connection failed'}
        </div>
      )}
      {!testMut.isPending && testMut.isError && (
        <div className="mt-3 text-xs" style={{ color: 'var(--color-danger, #ef4444)' }}>
          ✕ {testMut.error instanceof Error ? testMut.error.message : 'Test failed'}
        </div>
      )}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={handleTest}
          disabled={testMut.isPending}
          className="btn btn-ghost text-xs"
        >
          {testMut.isPending ? 'Testing…' : 'Test'}
        </button>
        <button
          type="button"
          onClick={() => openEditDrawer(workspace.id)}
          className="btn btn-ghost text-xs"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleteMut.isPending}
          className="btn btn-error text-xs"
        >
          {deleteMut.isPending ? 'Deleting…' : 'Delete'}
        </button>
      </div>
    </div>
  );
}

export default WorkspaceCard;
