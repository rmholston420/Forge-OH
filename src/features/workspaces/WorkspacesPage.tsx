'use client';
import { useWorkspaces } from './hooks';
import { useWorkspacesStore } from './store';
import { WorkspaceCard } from './WorkspaceCard';
import { WorkspaceFormDrawer } from './WorkspaceFormDrawer';
import { DeleteConfirmDialog } from './DeleteConfirmDialog';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { WorkspaceType } from './schemas';

const FILTER_TABS: { label: string; value: WorkspaceType | 'all' }[] = [
  { label: 'All',    value: 'all'    },
  { label: 'Local',  value: 'local'  },
  { label: 'Docker', value: 'docker' },
  { label: 'E2B',    value: 'e2b'    },
  { label: 'Modal',  value: 'modal'  },
];

export default function WorkspacesPage() {
  const { data: workspaces = [], isLoading } = useWorkspaces();
  const { filterType, setFilterType, openCreateDrawer } = useWorkspacesStore();

  const filtered = filterType === 'all'
    ? workspaces
    : workspaces.filter(w => w.type === filterType);

  return (
    <div className="workspaces-page">
      <div className="page-header">
        <h1>Workspaces</h1>
        <CanDo permission={Permission.WORKSPACES_CREATE}>
          <button className="btn btn-primary" onClick={openCreateDrawer}>
            New workspace
          </button>
        </CanDo>
      </div>

      <div className="filter-tabs" role="tablist" aria-label="Filter workspaces by type">
        {FILTER_TABS.map(tab => (
          <button
            key={tab.value}
            role="tab"
            aria-selected={filterType === tab.value}
            className={`filter-tab ${filterType === tab.value ? 'filter-tab--active' : ''}`}
            onClick={() => setFilterType(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="workspace-grid">
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 200, borderRadius: 8 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🗂️</div>
          <h3>{filterType === 'all' ? 'No workspaces yet' : `No ${filterType} workspaces`}</h3>
          <p>Workspaces are isolated environments for agent runs.</p>
          <CanDo permission={Permission.WORKSPACES_CREATE}>
            <button className="btn btn-primary" onClick={openCreateDrawer}>
              Create workspace
            </button>
          </CanDo>
        </div>
      ) : (
        <div className="workspace-grid">
          {filtered.map(ws => <WorkspaceCard key={ws.id} workspace={ws} />)}
        </div>
      )}

      <WorkspaceFormDrawer />
      <DeleteConfirmDialog />
    </div>
  );
}
