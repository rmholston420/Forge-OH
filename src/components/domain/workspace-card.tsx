import React from 'react';
import type { Workspace } from '@/features/workspaces/schemas';
import { WorkspaceHealthBadge } from './workspace-health-badge';
import { formatRelativeTime } from '@/lib/utils/format';

const TYPE_ICONS: Record<string, string> = {
  local: '💾',
  docker: '🐳',
  'remote-api': '☁️',
};

const TYPE_LABELS: Record<string, string> = {
  local: 'Local',
  docker: 'Docker',
  'remote-api': 'Remote API',
};

interface WorkspaceCardProps {
  workspace: Workspace;
  isSelected?: boolean;
  onSelect?: (id: string) => void;
  onReset?: (id: string) => void;
  onDuplicate?: (id: string) => void;
  onDelete?: (id: string) => void;
  onOpenDrawer?: (id: string) => void;
}

export function WorkspaceCard({
  workspace,
  isSelected = false,
  onSelect,
  onReset,
  onDuplicate,
  onDelete,
  onOpenDrawer,
}: WorkspaceCardProps) {
  const { id, name, type, health, agentServerUrl, runCount, activeRunId, lastSeenAt } = workspace;

  return (
    <article
      className={`workspace-card${isSelected ? ' workspace-card--selected' : ''}`}
      aria-pressed={isSelected}
      onClick={() => onSelect?.(id)}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect?.(id)}
    >
      <header className="workspace-card__header">
        <div className="workspace-card__type-badge">
          <span aria-hidden="true">{TYPE_ICONS[type ?? 'local']}</span>
          <span className="workspace-card__type-label">{TYPE_LABELS[type ?? 'local']}</span>
        </div>
        <WorkspaceHealthBadge health={health ?? 'healthy'} />
      </header>

      <h3 className="workspace-card__name">{name}</h3>

      {agentServerUrl && (
        <p className="workspace-card__url" title={agentServerUrl}>
          {agentServerUrl.length > 40 ? `${agentServerUrl.slice(0, 40)}…` : agentServerUrl}
        </p>
      )}

      <footer className="workspace-card__footer">
        <span className="workspace-card__meta">
          {runCount} run{runCount !== 1 ? 's' : ''}
          {activeRunId && <span className="workspace-card__active-dot" aria-label="Active run" />}
        </span>
        {lastSeenAt && (
          <span className="workspace-card__meta workspace-card__meta--muted">
            {formatRelativeTime(lastSeenAt)}
          </span>
        )}
      </footer>

      <div className="workspace-card__actions" role="group" aria-label="Workspace actions">
        <button
          className="btn btn-ghost btn-sm"
          onClick={(e) => { e.stopPropagation(); onOpenDrawer?.(id); }}
          aria-label={`View details for ${name}`}
        >
          Details
        </button>
        <button
          className="btn btn-ghost btn-sm"
          onClick={(e) => { e.stopPropagation(); onReset?.(id); }}
          aria-label={`Reset workspace ${name}`}
        >
          Reset
        </button>
        <button
          className="btn btn-ghost btn-sm"
          onClick={(e) => { e.stopPropagation(); onDuplicate?.(id); }}
          aria-label={`Duplicate workspace ${name}`}
        >
          Duplicate
        </button>
        <button
          className="btn btn-ghost btn-sm btn-destructive"
          onClick={(e) => { e.stopPropagation(); onDelete?.(id); }}
          aria-label={`Delete workspace ${name}`}
        >
          Delete
        </button>
      </div>
    </article>
  );
}
