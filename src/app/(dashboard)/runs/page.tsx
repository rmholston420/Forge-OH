'use client';
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/core/Button';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import { Modal } from '@/components/core/Modal';
import { RunCard } from '@/components/domain/RunCard';
import { NewRunComposer } from '@/components/domain/NewRunComposer';
import { useRuns } from '@/features/runs/hooks';
import { useRunsStore } from '@/features/runs/store';
import type { RunSummary } from '@/lib/schemas/run';
import styles from './runs.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_RUNS_HOME_ENABLED !== 'false';

function applyFilter(runs: RunSummary[], filter: { status?: string; workspaceType?: string; search?: string }) {
  return runs.filter((r) => {
    if (filter.status && r.status !== filter.status) return false;
    if (filter.workspaceType && r.workspaceType !== filter.workspaceType) return false;
    if (filter.search && !r.title.toLowerCase().includes(filter.search.toLowerCase())) return false;
    return true;
  });
}

export default function RunsPage() {
  const router = useRouter();
  const { data: runs, isLoading, isError, error } = useRuns();
  const { filter, setFilter, composerOpen, setComposerOpen } = useRunsStore();
  const [search, setSearch] = useState('');

  if (!FEATURE_ENABLED) {
    return (
      <div className={styles.page}>
        <Banner variant="info">Runs Home is feature-flagged. Set NEXT_PUBLIC_FEATURE_RUNS_HOME_ENABLED=true to enable.</Banner>
      </div>
    );
  }

  const filtered = runs ? applyFilter(runs, { ...filter, search }) : [];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <h1 className={styles.title}>Runs</h1>
          {runs && <span className={styles.count}>{runs.length}</span>}
        </div>
        <div className={styles.actions}>
          <input
            className={styles.search}
            type="search"
            placeholder="Search runs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search runs"
          />
          <select
            className={styles.filterSelect}
            value={filter.workspaceType ?? ''}
            onChange={(e) => setFilter({ workspaceType: (e.target.value as any) || undefined })}
            aria-label="Filter by workspace type"
          >
            <option value="">All workspaces</option>
            <option value="local">Local</option>
            <option value="docker">Docker</option>
            <option value="remote_api">Remote API</option>
          </select>
          <select
            className={styles.filterSelect}
            value={filter.status ?? ''}
            onChange={(e) => setFilter({ status: (e.target.value as any) || undefined })}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="awaiting_approval">Awaiting Approval</option>
            <option value="paused">Paused</option>
          </select>
          <Button variant="primary" onClick={() => setComposerOpen(true)}>New Run</Button>
        </div>
      </div>

      {isError && (
        <Banner variant="error">
          Failed to load runs: {error instanceof Error ? error.message : 'Unknown error'}
        </Banner>
      )}

      {isLoading && (
        <div className={styles.list} aria-label="Loading runs">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={styles.skeletonRow}>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Skeleton width="55%" height={14} />
                <Skeleton width="30%" height={12} />
              </div>
              <Skeleton width={80} height={22} borderRadius="99px" />
            </div>
          ))}
        </div>
      )}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          title={runs?.length === 0 ? 'No runs yet' : 'No runs match your filters'}
          description={runs?.length === 0
            ? 'Launch your first run to get started with agent supervision.'
            : 'Try clearing the filters to see all runs.'}
          action={runs?.length === 0
            ? <Button variant="primary" onClick={() => setComposerOpen(true)}>New Run</Button>
            : <Button variant="tertiary" onClick={() => { setFilter({}); setSearch(''); }}>Clear filters</Button>
          }
          icon="▶"
        />
      )}

      {!isLoading && filtered.length > 0 && (
        <div className={styles.list} role="list" aria-label="Runs">
          {filtered.map((run) => (
            <div key={run.id} role="listitem">
              <RunCard run={run} />
            </div>
          ))}
        </div>
      )}

      <Modal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        title="New Run"
        size="md"
      >
        <NewRunComposer
          onSuccess={(id) => { setComposerOpen(false); router.push(`/runs/${id}`); }}
          onCancel={() => setComposerOpen(false)}
        />
      </Modal>
    </div>
  );
}
