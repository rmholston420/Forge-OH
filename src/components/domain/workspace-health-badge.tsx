import React from 'react';
import type { WorkspaceHealth } from '@/features/workspaces/schemas';

const HEALTH_CONFIG: Record<
  WorkspaceHealth,
  { label: string; icon: string; colorVar: string }
> = {
  healthy: { label: 'Healthy', icon: '✓', colorVar: 'var(--color-state-success)' },
  warning: { label: 'Warning', icon: '⚠', colorVar: 'var(--color-state-warning)' },
  error: { label: 'Error', icon: '✕', colorVar: 'var(--color-state-error)' },
  disconnected: { label: 'Disconnected', icon: '○', colorVar: 'var(--color-text-muted)' },
};

interface WorkspaceHealthBadgeProps {
  health: WorkspaceHealth;
  size?: 'sm' | 'md';
}

export function WorkspaceHealthBadge({ health, size = 'md' }: WorkspaceHealthBadgeProps) {
  const { label, icon, colorVar } = HEALTH_CONFIG[health];

  return (
    <span
      className={`workspace-health-badge workspace-health-badge--${size}`}
      style={{ color: colorVar, borderColor: colorVar }}
      role="status"
      aria-label={`Workspace health: ${label}`}
    >
      {/* Icon + text: never color-only for accessibility */}
      <span aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </span>
  );
}
