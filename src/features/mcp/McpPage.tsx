'use client';
import { useMcpServers } from './hooks';
import { useMcpStore } from './store';
import { McpServerCard } from './McpServerCard';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { McpStatus } from './schemas';

const STATUS_FILTERS: { label: string; value: McpStatus | 'all' }[] = [
  { label: 'All',          value: 'all'          },
  { label: 'Connected',    value: 'connected'    },
  { label: 'Disconnected', value: 'disconnected' },
  { label: 'Error',        value: 'error'        },
];

export default function McpPage() {
  const { data: servers = [], isLoading } = useMcpServers();
  const { statusFilter, setStatusFilter, openRegisterDrawer } = useMcpStore();

  const filtered = statusFilter === 'all'
    ? servers
    : servers.filter(s => s.status === statusFilter);

  const totalTools = servers.reduce((sum, s) => sum + (s.toolCount ?? 0), 0);

  return (
    <div className="mcp-page">
      <div className="page-header">
        <div>
          <h1>MCP Servers</h1>
          <p className="page-subtitle">
            {servers.length} server{servers.length !== 1 ? 's' : ''} · {totalTools} tools available
          </p>
        </div>
        <CanDo permission={Permission.MCP_TOGGLE}>
          <button className="btn btn-primary" onClick={openRegisterDrawer}>
            Register server
          </button>
        </CanDo>
      </div>

      <div className="filter-tabs" role="tablist" aria-label="Filter by status">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            role="tab"
            aria-selected={statusFilter === f.value}
            className={`filter-tab ${statusFilter === f.value ? 'filter-tab--active' : ''}`}
            onClick={() => setStatusFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="mcp-grid">
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 160, borderRadius: 8 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔌</div>
          <h3>{statusFilter === 'all' ? 'No MCP servers registered' : `No ${statusFilter} servers`}</h3>
          <p>MCP servers expose tools that agents can call during runs.</p>
          <CanDo permission={Permission.MCP_TOGGLE}>
            <button className="btn btn-primary" onClick={openRegisterDrawer}>
              Register server
            </button>
          </CanDo>
        </div>
      ) : (
        <div className="mcp-grid">
          {filtered.map(s => <McpServerCard key={s.id} server={s} />)}
        </div>
      )}
    </div>
  );
}
