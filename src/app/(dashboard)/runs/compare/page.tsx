'use client';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED !== 'false';

import React, { Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import { EmptyState } from '@/components/core/EmptyState';
import { DiffViewer } from '@/components/domain/DiffViewer';
import { RunDetailHeader } from '@/components/domain/RunDetailHeader';
import styles from './compare.module.css';

interface CompareResult {
  baseRunId: string;
  forkRunId: string;
  baseTitle: string;
  forkTitle: string;
  files: Array<{
    path: string;
    status: 'added' | 'modified' | 'deleted' | 'unchanged';
    additions: number;
    deletions: number;
    diff: string;
  }>;
  stats: {
    totalFiles: number;
    additions: number;
    deletions: number;
  };
}

function useCompare(baseId: string | null, forkId: string | null) {
  return useQuery<CompareResult>({
    queryKey: ['runs', 'compare', baseId, forkId],
    queryFn: async () => {
      if (!baseId || !forkId) throw new Error('Both run IDs are required');
      const res = await fetch(`/api/runs/compare?base=${baseId}&fork=${forkId}`);
      if (!res.ok) throw new Error(`Compare failed: ${res.status}`);
      return res.json();
    },
    enabled: Boolean(baseId && forkId),
    staleTime: 30_000,
  });
}

function ComparePageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const baseId = params.get('base');
  const forkId = params.get('fork');

  const { data, isLoading, error } = useCompare(baseId, forkId);

  if (!FEATURE_ENABLED) {
    return (
      <Banner variant="info">
        Run compare is feature-flagged. Set NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED=true.
      </Banner>
    );
  }

  if (!baseId || !forkId) {
    return (
      <EmptyState
        title="No runs selected"
        description="Navigate here via the Fork action on a run detail page."
        icon="🔀"
      />
    );
  }

  if (isLoading) {
    return (
      <div className={styles.skeletons}>
        <Skeleton width="100%" height={48} borderRadius="8px" />
        <Skeleton width="100%" height={320} borderRadius="8px" />
      </div>
    );
  }

  if (error) {
    return <Banner variant="error">Failed to load comparison: {(error as Error).message}</Banner>;
  }

  if (!data) return null;

  return (
    <div className={styles.root}>
      {/* Header strip */}
      <div className={styles.header}>
        <div className={styles.runStrip}>
          <button className={styles.backBtn} onClick={() => router.back()} aria-label="Back">
            ← Back
          </button>
          <div className={styles.runLabel}>
            <span className={styles.runBadge} data-variant="base">base</span>
            <span className={styles.runTitle}>{data.baseTitle}</span>
            <code className={styles.runId}>{data.baseRunId.slice(0, 8)}</code>
          </div>
          <span className={styles.vs}>vs</span>
          <div className={styles.runLabel}>
            <span className={styles.runBadge} data-variant="fork">fork</span>
            <span className={styles.runTitle}>{data.forkTitle}</span>
            <code className={styles.runId}>{data.forkRunId.slice(0, 8)}</code>
          </div>
        </div>
        <div className={styles.stats}>
          <span className={styles.statItem}>{data.stats.totalFiles} files</span>
          <span className={styles.statItem} data-variant="add">+{data.stats.additions}</span>
          <span className={styles.statItem} data-variant="del">−{data.stats.deletions}</span>
        </div>
      </div>

      {/* File list + diffs */}
      {data.files.length === 0 ? (
        <EmptyState
          title="No differences"
          description="The fork produced identical file changes to the base run."
          icon="✅"
        />
      ) : (
        <div className={styles.fileList}>
          {data.files.map((file) => (
            <section key={file.path} className={styles.fileSection}>
              <div className={styles.fileHeader}>
                <span className={styles.filePath}>{file.path}</span>
                <span className={styles.fileBadge} data-status={file.status}>
                  {file.status}
                </span>
                <span className={styles.fileStats}>
                  <span data-variant="add">+{file.additions}</span>
                  {' '}
                  <span data-variant="del">−{file.deletions}</span>
                </span>
              </div>
              {file.diff ? (
                <DiffViewer diff={file.diff} filename={file.path} />
              ) : (
                <div className={styles.noDiff}>No diff content available.</div>
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

export default function RunComparePage() {
  return (
    <Suspense fallback={<Skeleton width="100%" height={400} borderRadius="8px" />}>
      <ComparePageInner />
    </Suspense>
  );
}
