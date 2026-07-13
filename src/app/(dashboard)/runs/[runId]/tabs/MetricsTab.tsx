'use client';
import React from 'react';
import { useRunMetrics } from '@/features/observability/hooks';
import { MetricKPI } from '@/components/domain/MetricKPI';
import { Banner } from '@/components/core/Banner';
import styles from './MetricsTab.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_METRICS_ENABLED !== 'false';

function formatCost(usd: number) {
  return usd < 0.01 ? `<$0.01` : `$${usd.toFixed(4)}`;
}

function formatDurationMs(ms: number | null) {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

export default function MetricsTab({ runId, isActive }: { runId: string; isActive: boolean }) {
  const { data: metrics, isLoading, error } = useRunMetrics(runId, isActive);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Metrics tab is feature-flagged. Set NEXT_PUBLIC_FEATURE_METRICS_ENABLED=true.</Banner>;
  }

  if (error) return <Banner variant="error">Failed to load metrics.</Banner>;

  return (
    <div className={styles.root}>
      <div className={styles.kpiGrid}>
        <MetricKPI
          label="Tokens" value={metrics?.tokenCount ?? 0}
          icon="🔤" loading={isLoading}
        />
        <MetricKPI
          label="Tool Calls" value={metrics?.toolCallCount ?? 0}
          icon="🔧" loading={isLoading}
        />
        <MetricKPI
          label="Files Touched" value={metrics?.filesTouchedCount ?? 0}
          icon="📁" loading={isLoading}
        />
        <MetricKPI
          label="Cost" value={metrics ? formatCost(metrics.costUsd) : '—'}
          icon="💰" loading={isLoading}
        />
        <MetricKPI
          label="Duration" value={metrics ? formatDurationMs(metrics.durationMs) : '—'}
          icon="⏱" loading={isLoading}
        />
      </div>

      {metrics?.series && metrics.series.length > 0 && (
        <div className={styles.seriesSection}>
          <h3 className={styles.seriesHeading}>Time Series</h3>
          {metrics.series.map((s) => (
            <div key={s.name} className={styles.seriesRow}>
              <span className={styles.seriesName}>{s.name}</span>
              <span className={styles.seriesUnit}>{s.unit}</span>
              <span className={styles.seriesPoints}>{s.points.length} pts</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
