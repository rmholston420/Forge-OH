'use client';

import React from 'react';
import { MCPServerCard } from '@/components/domain/mcp-server-card';
import { PluginCard } from '@/components/domain/plugin-card';
import { EmptyState } from '@/components/core/empty-state';
import { Skeleton } from '@/components/core/skeleton';
import {
  useMCPServers,
  useToggleMCPServer,
  usePingMCPServer,
  usePlugins,
  useTogglePlugin,
} from '@/features/mcp/hooks';
import { useMCPStore } from '@/features/mcp/store';

export default function ToolsMCPPage() {
  const { activeTab, setActiveTab, pingInFlight, setPingInFlight, openPluginConfig } =
    useMCPStore();

  const { data: servers, isLoading: serversLoading } = useMCPServers();
  const { data: plugins, isLoading: pluginsLoading } = usePlugins();

  const toggleServer = useToggleMCPServer();
  const pingServer = usePingMCPServer();
  const togglePlugin = useTogglePlugin();

  function handlePing(id: string) {
    setPingInFlight(id, true);
    pingServer.mutate(id, { onSettled: () => setPingInFlight(id, false) });
  }

  return (
    <main className="tools-mcp-page">
      <header className="page-header">
        <h1 className="page-title">Tools &amp; MCP</h1>
      </header>

      {/* Tab bar */}
      <div className="tab-bar" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'mcp'}
          className={`tab${activeTab === 'mcp' ? ' tab--active' : ''}`}
          onClick={() => setActiveTab('mcp')}
        >
          MCP Servers
          {servers && (
            <span className="tab__count">{servers.length}</span>
          )}
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'plugins'}
          className={`tab${activeTab === 'plugins' ? ' tab--active' : ''}`}
          onClick={() => setActiveTab('plugins')}
        >
          Plugins
          {plugins && (
            <span className="tab__count">{plugins.length}</span>
          )}
        </button>
      </div>

      {/* MCP Servers panel */}
      {activeTab === 'mcp' && (
        <section aria-label="MCP Servers">
          {serversLoading ? (
            <div className="card-grid">
              {[0, 1, 2].map((i) => (
                <div key={i} className="mcp-server-card">
                  <Skeleton className="skeleton-heading" />
                  <Skeleton className="skeleton-text" />
                </div>
              ))}
            </div>
          ) : !servers || servers.length === 0 ? (
            <EmptyState
              icon="🔌"
              title="No MCP servers configured"
              description="Add an MCP server to expose tools to your agents."
            />
          ) : (
            <div className="card-grid">
              {servers.map((srv) => (
                <MCPServerCard
                  key={srv.id}
                  server={srv}
                  pingInFlight={pingInFlight.has(srv.id)}
                  onToggle={(id, enable) => toggleServer.mutate({ id, enable })}
                  onPing={handlePing}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Plugins panel */}
      {activeTab === 'plugins' && (
        <section aria-label="Plugins">
          {pluginsLoading ? (
            <div className="card-grid">
              {[0, 1].map((i) => (
                <div key={i} className="plugin-card">
                  <Skeleton className="skeleton-heading" />
                  <Skeleton className="skeleton-text" />
                </div>
              ))}
            </div>
          ) : !plugins || plugins.length === 0 ? (
            <EmptyState
              icon="🧩"
              title="No plugins installed"
              description="Browse the plugin registry to extend Forge-OH."
            />
          ) : (
            <div className="card-grid">
              {plugins.map((plugin) => (
                <PluginCard
                  key={plugin.id}
                  plugin={plugin}
                  onToggle={(id, enable) => togglePlugin.mutate({ id, enable })}
                  onConfigure={openPluginConfig}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
