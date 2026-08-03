'use client';
import React from 'react';
import { useMarketplacePlugins, useInstallFromMarketplace } from '@/features/plugins/hooks';
import { Banner } from '@/components/core/Banner';
import { Skeleton } from '@/components/core/Skeleton';
import { EmptyState } from '@/components/core/EmptyState';

export function PluginMarketplaceGrid() {
  const { data: plugins = [], isLoading, error, refetch, isFetching } = useMarketplacePlugins();
  const installMut = useInstallFromMarketplace();

  const handleInstall = (source: string | null) => {
    if (!source) return;
    installMut.mutate({ source });
  };

  if (isLoading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} width="100%" height={160} borderRadius="12px" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Banner variant="error">
        Failed to load marketplace: {error instanceof Error ? error.message : 'Unknown error'}
      </Banner>
    );
  }

  if (plugins.length === 0) {
    return (
      <EmptyState
        title="Marketplace is empty"
        description="The agent-server has no plugin catalog configured. See the OpenHands docs for how to seed a marketplace registry."
        icon="🛒"
      />
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          style={{
            padding: '6px 10px',
            fontSize: 12,
            borderRadius: 6,
            border: '1px solid var(--color-border, #334155)',
            background: 'transparent',
            color: 'inherit',
            cursor: isFetching ? 'wait' : 'pointer',
          }}
        >
          {isFetching ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
        {plugins.map((p) => (
          <article
            key={p.id}
            style={{
              padding: 14,
              borderRadius: 12,
              border: '1px solid var(--color-border, #334155)',
              background: 'var(--color-surface, #0f172a)',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{p.name}</h3>
              {p.installed && (
                <span
                  style={{
                    fontSize: 10,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: 'var(--color-success, #10b981)',
                    color: 'white',
                  }}
                >
                  Installed
                </span>
              )}
            </div>
            {p.description && (
              <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-muted, #94a3b8)', minHeight: 30 }}>
                {p.description}
              </p>
            )}
            {p.skills.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {p.skills.slice(0, 4).map((s) => (
                  <span
                    key={s}
                    style={{
                      fontSize: 10,
                      padding: '2px 6px',
                      borderRadius: 4,
                      border: '1px solid var(--color-border, #334155)',
                      color: 'var(--color-text-muted, #94a3b8)',
                    }}
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
            {p.source && (
              <code style={{ fontSize: 10, color: 'var(--color-text-muted, #64748b)', wordBreak: 'break-all' }}>
                {p.source}
              </code>
            )}
            <button
              onClick={() => handleInstall(p.source)}
              disabled={p.installed || installMut.isPending || !p.source}
              style={{
                marginTop: 4,
                padding: '6px 10px',
                fontSize: 12,
                borderRadius: 6,
                border: '1px solid var(--color-border, #334155)',
                background: p.installed ? 'transparent' : 'var(--color-primary, #3b82f6)',
                color: p.installed ? 'var(--color-text-muted, #64748b)' : 'white',
                cursor: p.installed ? 'default' : 'pointer',
                opacity: installMut.isPending && !p.installed ? 0.6 : 1,
              }}
            >
              {p.installed ? 'Installed' : installMut.isPending ? 'Installing…' : 'Install'}
            </button>
          </article>
        ))}
      </div>
      {installMut.isError && (
        <Banner variant="error">
          Install failed: {installMut.error instanceof Error ? installMut.error.message : 'Unknown error'}
        </Banner>
      )}
    </div>
  );
}

export default PluginMarketplaceGrid;
