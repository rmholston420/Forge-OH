'use client';

import React from 'react';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';
import { StatusBadge } from '@/components/core/Badge';
import { Button } from '@/components/core/Button';
import styles from './runs.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_RUNS_HOME_ENABLED === 'true';

export default function RunsPage() {
  if (!FEATURE_ENABLED) {
    return (
      <div className={styles.page}>
        <div className={styles.header}>
          <h1 className={styles.title}>Runs</h1>
          <Button variant="primary" disabled>New Run</Button>
        </div>
        <EmptyState
          title="Runs coming in Slice 1A"
          description="The runs list and launcher will be implemented in Phase 1, Slice 1A."
          icon="▶"
        />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Runs</h1>
        <Button variant="primary">New Run</Button>
      </div>
      <div className={styles.skeletonList}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className={styles.skeletonRow}>
            <Skeleton width="30%" height={14} />
            <Skeleton width="10%" height={14} />
            <Skeleton width="15%" height={14} />
          </div>
        ))}
      </div>
    </div>
  );
}
