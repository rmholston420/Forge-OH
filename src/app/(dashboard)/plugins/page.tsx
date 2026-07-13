'use client';
import React from 'react';
import { usePlugins, useInstallPlugin } from '@/features/plugins/hooks';
import { usePluginsStore } from '@/features/plugins/store';
import { PluginCard } from '@/components/domain/PluginCard';
import { EmptyState } from '@/components/core/EmptyState';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import type { PluginStatus } from '@/lib/schemas/plugin';
import styles from './plugins.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_PLUGINS_ENABLED !== 'false';

const STATUS_LABELS: Record<PluginStatus | 'all', string> = {
  all: 'All',
  enabled: 'Enabled',
  disabled: 'Disabled',
  error: 'Error',
  installing: 'Installing',
};

export default function PluginsPage() {
  const { statusFilter, setStatusFilter } = usePluginsStore();
  const { data: plugins = [], isLoading, error } = usePlugins();

  const filtered = statusFilter === 'all'
    ? plugins
    : plugins.filter((p) => p.status === statusFilter);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">MCP Plugins are feature-flagged. Set NEXT_PUBLIC_FEATURE_PLUGINS_ENABLED=true.</Banner>;
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <div className={styles.filters} role="group" aria-label="Filter by status">
          {(['all', 'enabled', 'disabled', 'error'] as (PluginStatus | 'all')[]).map((s) => (
            <button
              key={s}
              className={[styles.filterBtn, statusFilter === s ? styles['filterBtn--active'] : ''].filter(Boolean).join(' ')}
              onClick={() => setStatusFilter(s)}
              aria-pressed={statusFilter === s}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <a
          href="https://github.com/modelcontextprotocol/servers"
          target="_blank"
          rel="noopener noreferrer"
          className={styles.browseLink}
        >
          Browse MCP Registry ↗
        </a>
      </div>

      {error && (
        <Banner variant="error">Failed to load plugins: {error instanceof Error ? error.message : 'Error'}</Banner>
      )}

      {isLoading ? (
        <div className={styles.grid}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} width="100%" height={200} borderRadius="12px" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No plugins installed"
          description="MCP plugins extend the agent with tools, resources, and prompts."
          icon="🧩"
        />
      ) : (
        <div className={styles.grid}>
          {filtered.map((plugin) => (
            <PluginCard key={plugin.id} plugin={plugin} />
          ))}
        </div>
      )}
    </div>
  );
}
