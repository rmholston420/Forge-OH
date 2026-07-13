'use client';

import React from 'react';
import { WorkspaceCard } from '@/components/domain/workspace-card';
import { WorkspaceDetailsDrawer } from '@/components/domain/workspace-details-drawer';
import { EmptyState } from '@/components/core/empty-state';
import { Skeleton } from '@/components/core/skeleton';
import {
  useWorkspaces,
  useWorkspace,
  useResetWorkspace,
  useDeleteWorkspace,
  useDuplicateWorkspace,
} from '@/features/workspaces/hooks';
import { useWorkspacesStore } from '@/features/workspaces/store';
import type { WorkspaceHealth } from '@/features/workspaces/schemas';

const HEALTH_FILTERS: Array<{ value: WorkspaceHealth | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'healthy', label: 'Healthy' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'disconnected', label: 'Disconnected' },
];

export default function WorkspacesPage() {
  const { data: workspaces, isLoading, error } = useWorkspaces();
  const {
    selectedWorkspaceId,
    drawerOpen,
    healthFilter,
    confirmResetId,
    openDrawer,
    closeDrawer,
    setHealthFilter,
    setSelectedWorkspaceId,
    setConfirmResetId,
  } = useWorkspacesStore();

  const { data: drawerWorkspace } = useWorkspace(drawerOpen ? selectedWorkspaceId : null);
  const resetMutation = useResetWorkspace();
  const deleteMutation = useDeleteWorkspace();
  const duplicateMutation = useDuplicateWorkspace();

  const filtered = (workspaces ?? []).filter(
    (w) => healthFilter === 'all' || w.health === healthFilter,
  );

  function handleReset(id: string) {
    setConfirmResetId(id);
  }

  function handleDoReset() {
    if (confirmResetId) {
      resetMutation.mutate(confirmResetId, {
        onSuccess: () => setConfirmResetId(null),
      });
    }
  }

  return (
    <main className="workspaces-page">
      <header className="page-header">
        <h1 className="page-title">Workspaces</h1>
        <button className="btn btn-primary btn-sm">
          + New Workspace
        </button>
      </header>

      {/* Health filter pills */}
      <div className="filter-pills" role="group" aria-label="Filter by health">
        {HEALTH_FILTERS.map(({ value, label }) => (
          <button
            key={value}
            className={`filter-pill${healthFilter === value ? ' filter-pill--active' : ''}`}
            onClick={() => setHealthFilter(value as WorkspaceHealth | 'all')}
            aria-pressed={healthFilter === value}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="workspace-grid">
          {[0, 1, 2].map((i) => (
            <div key={i} className="workspace-card workspace-card--skeleton">
              <Skeleton className="skeleton-heading" />
              <Skeleton className="skeleton-text" />
              <Skeleton className="skeleton-text" style={{ width: '60%' }} />
            </div>
          ))}
        </div>
      ) : error ? (
        <EmptyState
          icon="⚠"
          title="Failed to load workspaces"
          description="Check your BFF connection and try again."
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon="🗂️"
          title={healthFilter === 'all' ? 'No workspaces yet' : `No ${healthFilter} workspaces`}
          description={
            healthFilter === 'all'
              ? 'Create a workspace to start running agents.'
              : 'Try a different filter.'
          }
          action={
            healthFilter === 'all' ? (
              <button className="btn btn-primary">Create Workspace</button>
            ) : undefined
          }
        />
      ) : (
        <div className="workspace-grid">
          {filtered.map((ws) => (
            <WorkspaceCard
              key={ws.id}
              workspace={ws}
              isSelected={selectedWorkspaceId === ws.id}
              onSelect={setSelectedWorkspaceId}
              onReset={handleReset}
              onDuplicate={(id) =>
                duplicateMutation.mutate({ id, name: `${ws.name} (copy)` })
              }
              onDelete={(id) => deleteMutation.mutate(id)}
              onOpenDrawer={openDrawer}
            />
          ))}
        </div>
      )}

      {/* Details drawer */}
      <WorkspaceDetailsDrawer
        workspace={drawerWorkspace}
        open={drawerOpen}
        onClose={closeDrawer}
        onReset={handleReset}
        onConfirmReset={confirmResetId !== null}
        onCancelReset={() => setConfirmResetId(null)}
        onDoReset={handleDoReset}
      />
    </main>
  );
}
