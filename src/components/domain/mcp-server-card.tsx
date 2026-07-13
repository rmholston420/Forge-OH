import React from 'react';
import type { MCPServer, MCPServerStatus } from '@/features/mcp/schemas';

const STATUS_CONFIG: Record<
  MCPServerStatus,
  { label: string; icon: string; colorVar: string }
> = {
  connected: { label: 'Connected', icon: '●', colorVar: 'var(--color-state-success)' },
  disconnected: { label: 'Disconnected', icon: 'plug', colorVar: 'var(--color-text-muted)' },
  warning: { label: 'Warning', icon: 'alert-triangle', colorVar: 'var(--color-warning)' },
  connecting: { label: 'Connecting…', icon: '◔', colorVar: 'var(--color-state-running)' },
  error: { label: 'Error', icon: '✕', colorVar: 'var(--color-state-error)' },
  disabled: { label: 'Disabled', icon: '○', colorVar: 'var(--color-text-muted)' },
};

interface MCPServerCardProps {
  server: MCPServer;
  pingInFlight: boolean;
  onToggle: (id: string, enable: boolean) => void;
  onPing: (id: string) => void;
}

export function MCPServerCard({ server, pingInFlight, onToggle, onPing }: MCPServerCardProps) {
  const { id, name, url, status, toolCount, lastPingMs, version, description } = server;
  const cfg = STATUS_CONFIG[status ?? 'disconnected'];
  const isDisabled = status === 'disabled';

  return (
    <article className="mcp-server-card">
      <header className="mcp-server-card__header">
        <h3 className="mcp-server-card__name">{name}</h3>
        <span
          className="status-chip"
          style={{ color: cfg.colorVar }}
          role="status"
          aria-label={`MCP server status: ${cfg.label}`}
        >
          <span aria-hidden="true">{cfg.icon}</span>
          <span>{cfg.label}</span>
        </span>
      </header>

      {description && <p className="mcp-server-card__desc">{description}</p>}

      <p className="mcp-server-card__url">{url}</p>

      <div className="mcp-server-card__meta">
        <span className="badge">{toolCount} tools</span>
        {version && <span className="badge badge--secondary">v{version}</span>}
        {lastPingMs !== null && (
          <span className="badge badge--secondary">{lastPingMs}ms</span>
        )}
      </div>

      <div className="mcp-server-card__actions">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onPing(id)}
          disabled={pingInFlight || isDisabled}
          aria-label={`Ping MCP server ${name}`}
        >
          {pingInFlight ? 'Pinging…' : 'Ping Now'}
        </button>

        <label className="toggle-switch" aria-label={`${isDisabled ? 'Enable' : 'Disable'} ${name}`}>
          <input
            type="checkbox"
            checked={!isDisabled}
            onChange={(e) => onToggle(id, e.target.checked)}
          />
          <span className="toggle-switch__track" />
        </label>
      </div>
    </article>
  );
}
