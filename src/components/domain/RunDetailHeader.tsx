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
  onReject?: () => void;
  /** Disable all controls (e.g. while a mutation is in flight). */
  busy?: boolean;
}

function formatSelectedModel(value?: string | null) {
  if (!value) return null;
  return value.replace(/^ollama\//, 'Ollama: ').replace(/^vllm\//, 'vLLM: ');
}

export const RunDetailHeader: React.FC<RunDetailHeaderProps> = ({
  run,
  onPause,
  onStop,
  onFork,
  onApprove,
  onReject,
  busy = false,
}) => {
  const isRunning = run.status === 'running' || run.status === 'pending';
  const isPaused = run.status === 'paused';
  const isAwaiting = run.status === 'awaiting_approval' || run.status === 'pending_approval';
  const selectedModelLabel = formatSelectedModel(run.selectedModel ?? run.routing?.selected ?? null);

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
          {selectedModelLabel && (
            <span className={styles.chip}>
              <span aria-hidden="true">🧠</span> {selectedModelLabel}
            </span>
          )}
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
            <>
              <button
                className={[styles.btn, styles['btn--approve']].join(' ')}
                onClick={onApprove}
                aria-label="Approve pending action"
                disabled={busy}
              >
                ✓ Approve
              </button>
              <button
                className={[styles.btn, styles['btn--danger']].join(' ')}
                onClick={onReject}
                aria-label="Reject pending action"
                disabled={busy}
              >
                ✗ Reject
              </button>
            </>
          )}
          {(isRunning || isPaused) && (
            <button
              className={[styles.btn, styles['btn--secondary']].join(' ')}
              onClick={onPause}
              aria-label={isPaused ? 'Resume run' : 'Pause run'}
              disabled={busy}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>
          )}
          {(isRunning || isPaused) && (
            <button
              className={[styles.btn, styles['btn--danger']].join(' ')}
              onClick={onStop}
              aria-label="Stop run"
              disabled={busy}
            >
              ■ Stop
            </button>
          )}
          <button
            className={[styles.btn, styles['btn--secondary']].join(' ')}
            onClick={onFork}
            aria-label="Fork run"
            disabled={busy}
          >
            ⎇ Fork
          </button>
        </div>
      </div>
    </div>
  );
};
