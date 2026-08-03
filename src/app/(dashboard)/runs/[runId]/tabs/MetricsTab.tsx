'use client';
import React from 'react';
import { useRunMetrics } from '@/features/observability/hooks';
import { useTraceSpans } from '@/features/trace/hooks';
import { MetricKPI } from '@/components/domain/MetricKPI';
import { VerifyIterationsWidget } from '@/components/domain/VerifyIterationsWidget';
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

export function MetricsTab({ runId, isActive }: { runId: string; isActive: boolean }) {
  const { data: metrics, isLoading, isFetching, error } = useRunMetrics(runId, isActive);
  const { data: spans = [] } = useTraceSpans(runId);

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Metrics tab is feature-flagged. Set NEXT_PUBLIC_FEATURE_METRICS_ENABLED=true.</Banner>;
  }

  if (error) {
    const msg = error instanceof Error ? error.message : String(error ?? 'unknown');
    return <Banner variant="error">Failed to load metrics: {msg}</Banner>;
  }

  // Show skeleton only on the *first* load; once we have any data (even zeros),
  // render values so a slow background refetch doesn't wipe the whole grid.
  const showSkeleton = isLoading && !metrics;

  return (
    <div className={styles.root} aria-busy={isFetching || undefined}>
      <div className={styles.kpiGrid}>
        <MetricKPI
          label="Tokens" value={metrics?.tokenCount ?? 0}
          icon="🔤" loading={showSkeleton}
        />
        <MetricKPI
          label="Tool Calls" value={metrics?.toolCallCount ?? 0}
          icon="🔧" loading={showSkeleton}
        />
        <MetricKPI
          label="Files Touched" value={metrics?.filesTouchedCount ?? 0}
          icon="📁" loading={showSkeleton}
        />
        <MetricKPI
          label="Cost" value={metrics ? formatCost(metrics.costUsd) : '—'}
          icon="💰" loading={showSkeleton}
        />
        <MetricKPI
          label="Duration" value={metrics ? formatDurationMs(metrics.durationMs) : '—'}
          icon="⏱" loading={showSkeleton}
        />
      </div>

      <div className={styles.verifyRow}>
        <VerifyIterationsWidget spans={spans} />
      </div>

      {metrics?.series && metrics.series.length > 0 && (
        <div className={styles.seriesSection}>
          <h3 className={styles.seriesHeading}>Time Series</h3>
          {metrics.series.map((s: { name: string; points: Array<{ value: number; recordedAt: string; unit?: string }> }) => (
            <div key={s.name} className={styles.seriesRow}>
              <span className={styles.seriesName}>{s.name}</span>
              <span className={styles.seriesUnit}>{(s.points?.[0]?.unit ?? '')}</span>
              <span className={styles.seriesPoints}>{s.points.length} pts</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default MetricsTab;
