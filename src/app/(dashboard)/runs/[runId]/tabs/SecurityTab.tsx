'use client';
import React from 'react';
import { useTrace } from '@/features/trace/hooks';
import { useTraceStore } from '@/features/trace/store';
import { SpanRow } from '@/components/domain/SpanRow';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import { EmptyState } from '@/components/core/EmptyState';
import styles from './SecurityTab.module.css';

const FEATURE_ENABLED = process.env.NEXT_PUBLIC_FEATURE_TRACE_ENABLED !== 'false';

function getAllSpanIds(span: import('@/lib/schemas/trace').Span | undefined): string[] {
  if (!span) return [];
  return [span.spanId ?? '', ...span.children.flatMap(getAllSpanIds)];
}

export function SecurityTab({ runId }: { runId: string }) {
  const { data: trace, isLoading, error } = useTrace(runId || '');
  const { selectedSpanId, expandAll, collapseAll } = useTraceStore();

  if (!FEATURE_ENABLED) {
    return <Banner variant="info">Trace explorer is feature-flagged. Set NEXT_PUBLIC_FEATURE_TRACE_ENABLED=true.</Banner>;
  }

  if (isLoading) return <Skeleton width="100%" height={400} borderRadius="12px" />;
  if (error)     return <Banner variant="error">Failed to load trace.</Banner>;
  if (!trace)    return <EmptyState title="No trace" description="This run has no OpenTelemetry trace yet." icon="🔍" />;

  const allIds = getAllSpanIds(((trace.rootSpan ?? trace.spans[0]) ?? trace.spans[0]));

  return (
    <div className={styles.root}>
      <div className={styles.toolbar}>
        <div className={styles.meta}>
          <code className={styles.traceId}>{trace.traceId.slice(0, 16)}…</code>
          <span className={styles.spanCount}>{trace.totalSpans} spans</span>
          {Boolean(trace.spans?.some((s) => s.status === 'error')) && <span className={styles.errorBadge}>⚠ Errors</span>}
        </div>
        <div className={styles.actions}>
          <button className={styles.actionBtn} onClick={() => expandAll()}>Expand all</button>
          <button className={styles.actionBtn} onClick={() => collapseAll()}>Collapse all</button>
        </div>
      </div>

      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>Span</th>
              <th className={styles.th}>Status</th>
              <th className={styles.th}>Duration</th>
              <th className={styles.th}>Timeline</th>
            </tr>
          </thead>
          <tbody>
            <SpanRow
              span={((trace.rootSpan ?? trace.spans[0]) ?? trace.spans[0])}
              depth={0}
              traceStartTime={trace.startTime || new Date().toISOString()}
              traceDurationMs={(trace as { durationMs?: number }).durationMs || 1}
            />
          </tbody>
        </table>
      </div>

      {selectedSpanId && (() => {
        const findSpan = (s: import('@/lib/schemas/trace').Span): import('@/lib/schemas/trace').Span | null => {
          if (s.spanId === selectedSpanId) return s;
          for (const c of s.children) {
            const found = findSpan(c);
            if (found) return found;
          }
          return null;
        };
        const span = findSpan(((trace.rootSpan ?? trace.spans[0]) ?? trace.spans[0]));
        if (!span) return null;
        return (
          <div className={styles.detailPanel}>
            <h3 className={styles.detailTitle}>{span.name}</h3>
            <pre className={styles.detailJson}>{JSON.stringify(span.attributes, null, 2)}</pre>
            {(span.events?.length ?? 0) > 0 && (
              <>
                <h4 className={styles.detailSubtitle}>Events ({(span.events?.length ?? 0)})</h4>
                {(span.events ?? []).map((ev, i) => (
                  <div key={i} className={styles.detailEvent}>
                    <code>{String((ev as { name?: unknown }).name ?? 'event')}</code>
                    <span>{new Date(String((ev as { timestamp?: string }).timestamp ?? new Date().toISOString())).toLocaleTimeString()}</span>
                  </div>
                ))}
              </>
            )}
          </div>
        );
      })()}
    </div>
  );
}

export default SecurityTab;
