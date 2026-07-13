// DEPRECATED — re-export shim. Rename consuming imports to McpServerCard (PascalCase) in a follow-up.
// TODO(foh-phase2): delete this file once all callers updated.
import React from 'react';
import type { Plugin, PluginStatus } from '@/features/mcp/schemas';

const STATUS_CONFIG: Record<PluginStatus, { label: string; colorVar: string }> = {
  enabled:         { label: 'Enabled',          colorVar: 'var(--color-state-success)' },
  disabled:        { label: 'Disabled',         colorVar: 'var(--color-text-muted)' },
  error:           { label: 'Error',            colorVar: 'var(--color-state-error)' },
  installed:       { label: 'Installed',        colorVar: 'var(--color-text-muted)' },
  updateavailable: { label: 'Update available', colorVar: 'var(--color-warning)' },
  installing:      { label: 'Installing…',      colorVar: 'var(--color-state-running)' },
};

interface McpServerCardProps {
  plugin: Plugin;
  onToggle: (id: string, enable: boolean) => void;
  onConfigure: (id: string) => void;
}

/** @deprecated Use PluginCard from './PluginCard' once MCP schema is unified. */
export function McpServerCard({ plugin, onToggle, onConfigure }: McpServerCardProps) {
  const { id, name, version, status, description, author, configSchema } = plugin;
  const cfg = STATUS_CONFIG[status ?? 'disabled'];
  const isEnabled = status === 'enabled';
  const hasConfig = !!configSchema && Object.keys(configSchema).length > 0;

  return (
    <article className="plugin-card">
      <header className="plugin-card__header">
        <h3 className="plugin-card__name">{name}</h3>
        <div className="plugin-card__badges">
          <span className="badge badge--secondary">v{version}</span>
          <span
            className="badge"
            style={{ color: cfg.colorVar }}
            role="status"
            aria-label={`Plugin status: ${cfg.label}`}
          >
            {cfg.label}
          </span>
        </div>
      </header>

      {description && <p className="plugin-card__desc">{description}</p>}
      {author && <p className="plugin-card__author">by {author}</p>}

      <div className="plugin-card__actions">
        {hasConfig && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => onConfigure(id)}
            aria-label={`Configure plugin ${name}`}
          >
            Configure
          </button>
        )}
        <label
          className="toggle-switch"
          aria-label={`${isEnabled ? 'Disable' : 'Enable'} plugin ${name}`}
        >
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => onToggle(id, e.target.checked)}
            disabled={status === 'installing'}
          />
          <span className="toggle-switch__track" />
        </label>
      </div>
    </article>
  );
}
