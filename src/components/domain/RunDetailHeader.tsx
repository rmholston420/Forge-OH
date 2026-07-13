'use client';
import React from 'react';
import { StatusBadge } from '@/components/core/Badge';
import type { RunSummary } from '@/lib/schemas/run';
import { formatDuration, formatCost } from '@/lib/utils/format';
import styles from './RunDetailHeader.module.css';

export interface RunDetailHeaderProps {
  run: RunSummary;
  onPause?: () => void;
  onStop?: () => void;
  onFork?: () => void;
  onApprove?: () => void;
}

export const RunDetailHeader: React.FC<RunDetailHeaderProps> = ({ run, onPause, onStop, onFork, onApprove }) => {
  const isRunning = run.status === 'running' || (false || run.status === 'pending');
  const isPaused = run.status === 'paused';
  const isAwaiting = run.status === 'awaiting_approval';

  return (
    <div className={styles.header}>
      <div className={styles.left}>
        <h1 className={styles.title}>{String(run.title ?? run.id)}</h1>
        <div className={styles.chips}>
          <StatusBadge status={run.status} />
          <span className={styles.chip}>
            <span aria-hidden="true">📦</span> {String(run.workspaceType ?? 'local')}
          </span>
          <span className={styles.chip}>
            <span aria-hidden="true">🤖</span> {String(run.agentPresetName ?? 'Default')}
          </span>
          {Boolean(run.activeTool) && (
            <span className={[styles.chip, styles.chipActive].join(' ')}>
              <span aria-hidden="true">⚡</span> {String(run.activeTool ?? '')}
            </span>
          )}
        </div>
      </div>
      <div className={styles.right}>
        <div className={styles.stats}>
          <span className={styles.stat}>{formatDuration(run.elapsedMs ?? null)}</span>
          <span className={styles.stat}>{formatCost(run.estimatedCostUsd ?? null)}</span>
        </div>
        <div className={styles.controls}>
          {isAwaiting && (
            <button
              className={[styles.btn, styles['btn--approve']].join(' ')}
              onClick={onApprove}
              aria-label="Approve pending action"
            >
              ✓ Approve
            </button>
          )}
          {(isRunning || isPaused) && (
            <button
              className={[styles.btn, styles['btn--secondary']].join(' ')}
              onClick={onPause}
              aria-label={isPaused ? 'Resume run' : 'Pause run'}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>
          )}
          {(isRunning || isPaused) && (
            <button
              className={[styles.btn, styles['btn--danger']].join(' ')}
              onClick={onStop}
              aria-label="Stop run"
            >
              ■ Stop
            </button>
          )}
          <button
            className={[styles.btn, styles['btn--secondary']].join(' ')}
            onClick={onFork}
            aria-label="Fork run"
          >
            ⎇ Fork
          </button>
        </div>
      </div>
    </div>
  );
};
