import React from 'react';
import styles from './StatusBadge.module.css';
import type { RunStatus } from '../../../lib/schemas/run';

export type StatusBadgeStatus = RunStatus;

const STATUS_LABELS: Record<StatusBadgeStatus, string> = {
  idle: 'Idle',
  running: 'Running',
  streaming: 'Streaming',
  queued: 'Queued',
  paused: 'Paused',
  awaiting_approval: 'Awaiting Approval',
  succeeded: 'Succeeded',
  failed: 'Failed',
  blocked: 'Blocked',
};

const STATUS_CSS_CLASS: Record<StatusBadgeStatus, string> = {
  idle: styles.idle,
  running: styles.running,
  streaming: styles.streaming,
  queued: styles.queued,
  paused: styles.paused,
  awaiting_approval: styles.awaitingApproval,
  succeeded: styles.succeeded,
  failed: styles.failed,
  blocked: styles.blocked,
};

export interface StatusBadgeProps {
  status: StatusBadgeStatus;
  /** Show a pulsing dot indicator (useful for live/running states) */
  dot?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

export function StatusBadge({ status, dot = false, size = 'md', className }: StatusBadgeProps) {
  const isLive = status === 'running' || status === 'streaming';
  const showDot = dot || isLive;

  return (
    <span
      className={[
        styles.badge,
        STATUS_CSS_CLASS[status],
        styles[`size-${size}`],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      aria-label={STATUS_LABELS[status]}
    >
      {showDot && (
        <span className={[styles.dot, isLive ? styles.dotPulse : ''].filter(Boolean).join(' ')} aria-hidden="true" />
      )}
      {STATUS_LABELS[status]}
    </span>
  );
}
