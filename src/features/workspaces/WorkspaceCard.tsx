'use client';
import { useResetWorkspace, useDeleteWorkspace } from './hooks';
import { useWorkspacesStore } from './store';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { Workspace } from './schemas';

const TYPE_STYLES: Record<string, string> = {
  local:  'badge badge--muted',
  docker: 'badge badge--blue',
  e2b:    'badge badge--purple',
  modal:  'badge badge--orange',
};

const STATUS_DOTS: Record<string, string> = {
  idle:         'status-dot status-dot--idle',
  active:       'status-dot status-dot--active',
  error:        'status-dot status-dot--error',
  provisioning: 'status-dot status-dot--provisioning',
};

export function WorkspaceCard({ workspace: ws }: { workspace: Workspace }) {
  const { openEditDrawer, openConfirmDelete } = useWorkspacesStore();
  const reset  = useResetWorkspace();

  const diskPct = Math.min(100, Math.round(((ws.diskUsageMb ?? 0) / ((ws.diskLimitMb ?? 1) || 1)) * 100));

  return (
    <article className="workspace-card" aria-label={ws.name}>
      <div className="workspace-card-header">
        <div className="workspace-card-title">
          <span className={STATUS_DOTS[ws.status ?? 'stopped']} aria-label={`Status: ${ws.status}`} />
          <h3>{ws.name}</h3>
        </div>
        <span className={TYPE_STYLES[ws.type ?? 'local']}>{ws.type}</span>
      </div>

      {ws.description && (
        <p className="workspace-card-desc">{ws.description}</p>
      )}

      <div className="workspace-card-stats">
        <div className="workspace-stat">
          <span className="workspace-stat-label">Runs</span>
          <span className="workspace-stat-value">{ws.runCount}</span>
        </div>
        <div className="workspace-stat">
          <span className="workspace-stat-label">Disk</span>
          <span className="workspace-stat-value">
            {ws.diskUsageMb}&nbsp;/&nbsp;{ws.diskLimitMb}&nbsp;MB
          </span>
        </div>
      </div>

      <div className="workspace-disk-bar">
        <progress
          value={diskPct}
          max={100}
          aria-label={`Disk usage: ${diskPct}%`}
          className={diskPct > 80 ? 'disk-bar disk-bar--warn' : 'disk-bar'}
        />
      </div>

      <div className="workspace-card-actions">
        <CanDo permission={Permission.WORKSPACES_EDIT}>
          <button
            className="btn btn-sm"
            onClick={() => openEditDrawer(ws.id)}
          >
            Edit
          </button>
        </CanDo>
        <CanDo permission={Permission.WORKSPACES_RESET}>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => reset.mutate(ws.id)}
            disabled={reset.isPending || ws.status === 'active'}
          >
            Reset
          </button>
        </CanDo>
        <CanDo permission={Permission.WORKSPACES_DELETE}>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => openConfirmDelete(ws.id, ws.name)}
          >
            Delete
          </button>
        </CanDo>
      </div>
    </article>
  );
}
