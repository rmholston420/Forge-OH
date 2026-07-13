import React from 'react';
import { clsx } from 'clsx';
import styles from './StatusBadge.module.css';
import type { RunStatus } from '@/lib/schemas/run';

/** Full run-state semantic color mapping per the Forge-OH State Language spec.
 *  This is intentionally distinct from Badge — Badge is for generic labels,
 *  StatusBadge carries the full semantic meaning of a Run's lifecycle state.
 */
export const STATUS_LABELS: Record<RunStatus, string> = {
  idle:              'Idle',
  running:           'Running',
  streaming:         'Streaming',
  queued:            'Queued',
  paused:            'Paused',
  awaiting_approval: 'Awaiting Approval',
  succeeded:         'Succeeded',
  failed:            'Failed',
  blocked:           'Blocked',
};

export interface StatusBadgeProps {
  status: RunStatus;
  /** Render a pulsing dot indicator alongside the label */
  showDot?: boolean;
  className?: string;
}

export function StatusBadge({ status, showDot = false, className }: StatusBadgeProps) {
  return (
    <span
      className={clsx(styles.badge, styles[`status-${status}`], className)}
      aria-label={`Status: ${STATUS_LABELS[status]}`}
    >
      {showDot && (
        <span
          className={clsx(styles.dot, isLiveState(status) && styles.dotPulse)}
          aria-hidden="true"
        />
      )}
      {STATUS_LABELS[status]}
    </span>
  );
}

function isLiveState(status: RunStatus): boolean {
  return status === 'running' || status === 'streaming';
}
