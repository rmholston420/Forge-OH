import React from 'react';
import styles from './Badge.module.css';

export type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'paused' | 'running' | 'accent' | 'muted';
export type BadgeSize = 'sm' | 'md';

export interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'default', size = 'md', children, className = '' }) => {
  const classes = [styles.badge, styles[`badge--${variant}`], styles[`badge--${size}`], className].join(' ');
  return <span className={classes}>{children}</span>;
};

export const StatusBadge: React.FC<{ status: string; className?: string }> = ({ status, className }) => {
  const variantMap: Record<string, BadgeVariant> = {
    idle: 'muted',
    running: 'running',
    streaming: 'running',
    queued: 'muted',
    paused: 'paused',
    awaiting_approval: 'warning',
    succeeded: 'success',
    failed: 'error',
    blocked: 'error',
  };
  const variant = variantMap[status] ?? 'default';
  return <Badge variant={variant} className={className}>{status.replace(/_/g, ' ')}</Badge>;
};
