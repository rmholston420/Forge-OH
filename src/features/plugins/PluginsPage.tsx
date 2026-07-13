'use client';
import { useState } from 'react';
import { usePlugins, usePingPlugin } from '@/lib/plugins/hooks';
import { CanDo } from '@/components/auth/CanDo';
import { Permission } from '@/lib/rbac/permissions';

export default function PluginsPage() {
  const { data: plugins = [], isLoading } = usePlugins();
  const ping = usePingPlugin();
  const [lastPing, setLastPing] = useState<Record<string, number>>({});

  async function handlePing(id: string) {
    const result = await ping.mutateAsync(id);
    setLastPing(prev => ({ ...prev, [id]: result.latencyMs }));
  }

  if (isLoading) {
    return (
      <div className="plugins-skeleton">
        {[1, 2, 3].map(i => (
          <div key={i} className="skeleton" style={{ height: 120, borderRadius: 8 }} />
        ))}
      </div>
    );
  }

  if (plugins.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🔌</div>
        <h3>No plugins registered</h3>
        <p>Register a Rigpa-LMS plugin to enable bidirectional event bridging.</p>
        <CanDo permission={Permission.PLUGINS_TOGGLE}>
          <button className="btn btn-primary">Register plugin</button>
        </CanDo>
      </div>
    );
  }

  return (
    <div className="plugins-page">
      <div className="plugins-header">
        <h1>Plugins</h1>
        <CanDo permission={Permission.PLUGINS_TOGGLE}>
          <button className="btn btn-primary">Register plugin</button>
        </CanDo>
      </div>

      <div className="plugins-grid">
        {plugins.map(plugin => (
          <div key={plugin.id} className="plugin-card">
            <div className="plugin-card-header">
              <span className="plugin-name">{plugin.name}</span>
              <span className="plugin-version">v{plugin.version}</span>
            </div>

            {plugin.description && (
              <p className="plugin-description">{plugin.description}</p>
            )}

            <div className="plugin-meta">
              <span className="plugin-url">{plugin.baseUrl}</span>
              {lastPing[plugin.id] !== undefined && (
                <span className="plugin-latency">{lastPing[plugin.id]}ms</span>
              )}
            </div>

            <div className="plugin-capabilities">
              {plugin.capabilities.slice(0, 4).map(cap => (
                <span key={cap} className="capability-chip">{cap.replace(/_/g, ' ')}</span>
              ))}
              {plugin.capabilities.length > 4 && (
                <span className="capability-chip">+{plugin.capabilities.length - 4}</span>
              )}
            </div>

            <div className="plugin-actions">
              <CanDo permission={Permission.MCP_PING}>
                <button
                  className="btn btn-sm"
                  onClick={() => handlePing(plugin.id)}
                  disabled={ping.isPending}
                >
                  Ping
                </button>
              </CanDo>
              <CanDo permission={Permission.PLUGINS_CONFIGURE}>
                <button className="btn btn-sm btn-ghost">Configure</button>
              </CanDo>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
