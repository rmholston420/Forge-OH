'use client';
import { usePingMcpServer, useToggleMcpServer, useDeleteMcpServer } from './hooks';
import { useMcpStore } from './store';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';
import type { McpServer } from './schemas';

const STATUS_CLASSES: Record<string, string> = {
  connected:    'badge badge--success',
  disconnected: 'badge badge--muted',
  error:        'badge badge--error',
  connecting:   'badge badge--warning',
};

const TRANSPORT_ICONS: Record<string, string> = {
  stdio: '⧉',  // terminal-like
  sse:   '📡',
  http:  '🌐',
};

export function McpServerCard({ server }: { server: McpServer }) {
  const ping   = usePingMcpServer();
  const toggle = useToggleMcpServer();
  const del    = useDeleteMcpServer();
  const { setConfirmDeleteId } = useMcpStore();

  return (
    <article className="mcp-card" aria-label={server.name}>
      <div className="mcp-card-header">
        <span className="mcp-transport-icon" aria-hidden="true">
          {TRANSPORT_ICONS[server.transport ?? 'stdio']}
        </span>
        <div className="mcp-card-title">
          <h3>{server.name}</h3>
          {server.description && (
            <p className="mcp-card-desc">{server.description}</p>
          )}
        </div>
        <span className={STATUS_CLASSES[server.status ?? 'disconnected']}>
          {server.status}
        </span>
      </div>

      <div className="mcp-card-meta">
        <span className="mcp-transport-badge">{server.transport}</span>
        <span className="mcp-tools-chip">
          {server.toolCount} {server.toolCount === 1 ? 'tool' : 'tools'}
        </span>
        {server.lastPingMs !== undefined && (
          <span className="mcp-latency">{server.lastPingMs}ms</span>
        )}
      </div>

      {(server.tags ?? []).length > 0 && (
        <div className="mcp-tags">
          {(server.tags ?? []).map(tag => (
            <span key={tag} className="mcp-tag">{tag}</span>
          ))}
        </div>
      )}

      <div className="mcp-card-actions">
        <CanDo permission={Permission.MCP_PING}>
          <button
            className="btn btn-sm"
            onClick={() => ping.mutate(server.id)}
            disabled={ping.isPending}
          >
            Ping
          </button>
        </CanDo>
        <CanDo permission={Permission.MCP_TOGGLE}>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => toggle.mutate(server.id)}
            disabled={toggle.isPending}
            aria-pressed={server.enabled}
          >
            {server.enabled ? 'Disable' : 'Enable'}
          </button>
        </CanDo>
        <CanDo permission={Permission.MCP_TOGGLE}>
          <button
            className="btn btn-sm btn-danger"
            onClick={() => setConfirmDeleteId(server.id)}
          >
            Remove
          </button>
        </CanDo>
      </div>
    </article>
  );
}
