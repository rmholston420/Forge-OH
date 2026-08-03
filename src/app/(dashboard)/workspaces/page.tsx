'use client';
import React from 'react';
import { useWorkspaces, useDeleteWorkspace, useTestWorkspaceConnection } from '@/features/workspaces/hooks';
import { useWorkspacesStore } from '@/features/workspaces/store';
import { WorkspaceCard } from '@/components/domain/WorkspaceCard';
import { WorkspaceFormModal } from '@/components/domain/WorkspaceFormModal';
import { EmptyState } from '@/components/core/EmptyState';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import styles from './workspaces.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_WORKSPACES_ENABLED !== 'false';

export default function WorkspacesPage() {
  const { composerOpen, editingId, openComposer, closeComposer } = useWorkspacesStore();
  const { data: workspaces = [], isLoading, error } = useWorkspaces();
  const deleteMutation = useDeleteWorkspace();
  const testMutation = useTestWorkspaceConnection();

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Workspaces are feature-flagged. Set NEXT_PUBLIC_FEATURE_WORKSPACES_ENABLED=true.</Banner>;
  }

  // Retained but currently unused — kept exported for future card actions.
  void deleteMutation;
  void testMutation;

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div />
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
      ) : workspaces.length === 0 ? (
        <EmptyState
          title="No workspaces"
          description="Create a workspace to give the agent a place to run."
          icon="🗂️"
          action={<button className={styles.newBtn} onClick={() => openComposer()}>New Workspace</button>}
        />
      ) : (
        <div className={styles.grid}>
          {workspaces.map((ws) => (
            <WorkspaceCard
              key={ws.id}
              workspace={ws}
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
