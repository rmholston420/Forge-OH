import { Badge } from '@/components/core/Badge';
import type { Workspace } from '@/lib/schemas/workspace';

const typeLabels: Record<'local' | 'docker' | 'remote_api' | 'remoteapi' | 'e2b' | 'modal', string> = {
  local: 'Local',
  docker: 'Docker',
  remote_api: 'Remote API',
  remoteapi: 'Remote API',
  e2b: 'E2B',
  modal: 'Modal',
};

const typeHints: Record<'local' | 'docker' | 'remote_api' | 'remoteapi' | 'e2b' | 'modal', string> = {
  local: 'filesystem',
  docker: 'container',
  remote_api: 'via API',
  remoteapi: 'via API',
  e2b: 'ephemeral',
  modal: 'serverless',
};

const statusColors: Record<'idle' | 'active' | 'inactive' | 'error' | 'provisioning', string> = {
  idle: 'muted',
  active: 'success',
  inactive: 'muted',
  error: 'danger',
  provisioning: 'warning',
};

type Props = {
  workspace: Workspace;
};

export function WorkspaceCard({ workspace }: Props) {
  const type = workspace.type ?? 'local';
  const status = workspace.status ?? 'idle';
  const health = workspace.health ?? 'healthy';
  const activeRunCount = workspace.activeRunCount ?? 0;

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{workspace.name}</h3>
          <p className="text-xs text-[var(--color-text-muted)]">
            {typeLabels[type]} · {typeHints[type]}
          </p>
        </div>
        <Badge variant={statusColors[status] as never}>{status}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-text-muted)]">
        <span>Health: {health}</span>
        <span>Runs: {workspace.runCount ?? 0}</span>
        <span>Active: {activeRunCount}</span>
        <span>
          Disk: {(workspace.diskUsageMb ?? 0).toFixed?.(0) ?? 0}/{(workspace.diskLimitMb ?? 0).toFixed?.(0) ?? 0} MB
        </span>
      </div>
    </div>
  );
}

export default WorkspaceCard;
