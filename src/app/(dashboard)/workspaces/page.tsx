'use client';
import React from 'react';
import { useWorkspaces, useDeleteWorkspace, useTestWorkspaceConnection } from '@/features/workspaces/hooks';
import { useWorkspacesStore } from '@/features/workspaces/store';
import { WorkspaceCard } from '@/components/domain/WorkspaceCard';
import { WorkspaceFormModal } from '@/components/domain/WorkspaceFormModal';
import { EmptyState } from '@/components/core/EmptyState';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import type { WorkspaceType } from '@/lib/schemas/workspace';
import styles from './workspaces.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_WORKSPACES_ENABLED !== 'false';

const TYPE_LABELS: Record<WorkspaceType | 'all', string> = {
  all: 'All',
  local: 'Local',
  docker: 'Docker',
  remote_api: 'Remote API',
};

export default function WorkspacesPage() {
  const { typeFilter, setTypeFilter, composerOpen, editingId, openComposer, closeComposer } = useWorkspacesStore();
  const { data: workspaces = [], isLoading, error } = useWorkspaces();
  const deleteMutation = useDeleteWorkspace();
  const testMutation = useTestWorkspaceConnection();

  const filtered = typeFilter === 'all' ? workspaces : workspaces.filter((w) => w.type === typeFilter);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Workspaces are feature-flagged. Set NEXT_PUBLIC_FEATURE_WORKSPACES_ENABLED=true.</Banner>;
  }

  const handleDelete = (id: string) => {
    if (confirm('Delete this workspace? This cannot be undone.')) {
      deleteMutation.mutate(id);
    }
  };

  const handleTest = async (id: string) => {
    const result = await testMutation.mutateAsync(id);
    alert(result.ok
      ? `✅ Connection OK (${result.latencyMs}ms)`
      : `❌ Connection failed: ${result.error}`);
  };

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div className={styles.filters} role="group" aria-label="Filter by type">
          {(['all', 'local', 'docker', 'remote_api'] as (WorkspaceType | 'all')[]).map((t) => (
            <button
              key={t}
              className={[styles.filterBtn, typeFilter === t ? styles['filterBtn--active'] : ''].filter(Boolean).join(' ')}
              onClick={() => setTypeFilter(t)}
              aria-pressed={typeFilter === t}
            >
              {TYPE_LABELS[t]}
            </button>
          ))}
        </div>
        <button className={styles.newBtn} onClick={() => openComposer()}>
          + New Workspace
        </button>
      </div>

      {error && (
        <Banner variant="error">Failed to load workspaces: {error instanceof Error ? error.message : 'Error'}</Banner>
      )}

      {isLoading ? (
        <div className={styles.grid}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} width="100%" height={180} borderRadius="12px" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No workspaces"
          description="Create a workspace to give the agent a place to run."
          icon="🐳"
          action={{ label: 'New Workspace', onClick: () => openComposer() }}
        />
      ) : (
        <div className={styles.grid}>
          {filtered.map((ws) => (
            <WorkspaceCard
              key={ws.id}
              workspace={ws}
              onEdit={openComposer}
              onDelete={handleDelete}
              onTest={handleTest}
            />
          ))}
        </div>
      )}

      <WorkspaceFormModal
        open={composerOpen}
        editingId={editingId}
        onClose={closeComposer}
      />
    </div>
  );
}
