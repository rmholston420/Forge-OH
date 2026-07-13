'use client';
import React from 'react';
import Link from 'next/link';
import { StatusBadge } from '@/components/core/Badge';
import type { RunSummary } from '@/lib/schemas/run';
import { formatDuration, formatCost, formatDate } from '@/lib/utils/format';
import styles from './RunCard.module.css';

export interface RunCardProps {
  run: RunSummary;
}

export const RunCard: React.FC<RunCardProps> = ({ run }) => {
  return (
    <Link href={`/runs/${run.id}`} className={styles.card}>
      <div className={styles.main}>
        <div className={styles.titleRow}>
          <span className={styles.title}>{run.title}</span>
          <StatusBadge status={run.status} />
        </div>
        <div className={styles.meta}>
          <span className={styles.chip}>
            <span aria-hidden="true">
              {run.workspaceType === 'docker' ? '📦' : run.workspaceType === 'remote_api' ? '🌐' : '💻'}
            </span>
            {run.workspaceType}
          </span>
          <span className={styles.chip}>
            <span aria-hidden="true">🤖</span>
            {run.agentPresetName}
          </span>
          {run.activeTool && (
            <span className={styles.chipActive}>
              <span aria-hidden="true">⚡</span>
              {run.activeTool}
            </span>
          )}
        </div>
      </div>
      <div className={styles.stats}>
        <span className={styles.stat}>{formatDuration(run.elapsedMs)}</span>
        <span className={styles.stat}>{formatCost(run.estimatedCostUsd)}</span>
        <span className={styles.statMeta}>{formatDate(run.updatedAt)}</span>
      </div>
    </Link>
  );
};
