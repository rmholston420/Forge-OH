import { Badge } from '@/components/core/Badge';
import type { Workspace } from '@/lib/schemas/workspace';

/**
 * Stage 6: workspaces are local-only. The card shows name + path and
 * exposes the raw agent-server registry info. Status/health/disk stats are
 * left as best-effort in case future stages populate them.
 */

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
  const status = workspace.status ?? 'idle';

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">{workspace.name}</h3>
          <p className="text-xs text-[var(--color-text-muted)]">Local · filesystem</p>
        </div>
        <Badge variant={statusColors[status] as never}>{status}</Badge>
      </div>

      <div className="mt-3 flex flex-col gap-1 text-xs text-[var(--color-text-muted)]">
        <span title={workspace.path} className="truncate font-mono">{workspace.path}</span>
      </div>
    </div>
  );
}

export default WorkspaceCard;
