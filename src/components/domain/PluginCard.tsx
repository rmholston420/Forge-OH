'use client';
import React from 'react';
import type { Plugin } from '@/lib/schemas/plugin';
import { useTogglePlugin, useUninstallPlugin, usePingPlugin } from '@/features/plugins/hooks';
import styles from './PluginCard.module.css';

const TRANSPORT_ICON: Record<Plugin['transport'], string> = {
  stdio: '💻',
  sse: '📡',
  http: '🌐',
};

const STATUS_CLASS: Record<Plugin['status'], string> = {
  enabled: 'enabled',
  disabled: 'disabled',
  error: 'error',
  installing: 'installing',
};

export interface PluginCardProps {
  plugin: Plugin;
}

export const PluginCard: React.FC<PluginCardProps> = ({ plugin }) => {
  const toggleMutation = useTogglePlugin();
  const uninstallMutation = useUninstallPlugin();
  const pingMutation = usePingPlugin();

  const handleToggle = () => {
    toggleMutation.mutate({ id: plugin.id, enabled: plugin.status !== 'enabled' });
  };

  const handlePing = async () => {
    const result = await pingMutation.mutateAsync(plugin.id);
    alert(result.ok ? `✅ Alive (${result.latencyMs}ms)` : '❌ No response');
  };

  const handleUninstall = () => {
    if (confirm(`Uninstall "${plugin.name}"? This cannot be undone.`)) {
      uninstallMutation.mutate(plugin.id);
    }
  };

  return (
    <article className={styles.card}>
      <div className={styles.header}>
        <span className={styles.icon} aria-hidden="true">{TRANSPORT_ICON[plugin.transport]}</span>
        <div className={styles.info}>
          <span className={styles.name}>{plugin.name}</span>
          <span className={styles.version}>v{plugin.version}</span>
        </div>
        <button
          className={[
            styles.toggle,
            plugin.status === 'enabled' ? styles['toggle--on'] : styles['toggle--off'],
          ].join(' ')}
          onClick={handleToggle}
          aria-label={plugin.status === 'enabled' ? 'Disable plugin' : 'Enable plugin'}
          aria-pressed={plugin.status === 'enabled'}
          disabled={plugin.status === 'installing'}
        >
          <span className={styles.toggleThumb} />
        </button>
      </div>

      {plugin.description && (
        <p className={styles.description}>{plugin.description}</p>
      )}

      <div className={styles.caps}>
        {plugin.capabilities.map((cap) => (
          <span key={cap} className={styles.cap}>{cap}</span>
        ))}
        <span className={[
          styles.statusBadge,
          styles[`statusBadge--${STATUS_CLASS[plugin.status]}`],
        ].join(' ')}>
          {plugin.status}
        </span>
      </div>

      <dl className={styles.meta}>
        <dt>Transport</dt><dd>{plugin.transport}</dd>
        {plugin.toolCount > 0 && <><dt>Tools</dt><dd>{plugin.toolCount}</dd></>}
        {plugin.command && <><dt>Command</dt><dd className={styles.code}>{plugin.command}</dd></>}
        {plugin.url && <><dt>URL</dt><dd className={styles.code}>{plugin.url}</dd></>}
      </dl>

      <div className={styles.actions}>
        <button
          className={styles.btn}
          onClick={handlePing}
          disabled={plugin.status !== 'enabled'}
          aria-label="Ping plugin"
        >
          Ping
        </button>
        <button
          className={[styles.btn, styles['btn--danger']].join(' ')}
          onClick={handleUninstall}
          aria-label="Uninstall plugin"
        >
          Uninstall
        </button>
      </div>
    </article>
  );
};
