'use client';
import React, { useState } from 'react';
import { useRuns } from '@/features/runs/hooks';
import { useTrace, useTraceSpans } from '@/features/observability/hooks';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import type { TraceSpan } from '@/lib/schemas/trace';

const KIND_COLOR: Record<string, string> = {
  llm: '#a855f7',
  tool: '#3b82f6',
  workspace: '#10b981',
  browser: '#f59e0b',
  network: '#06b6d4',
  internal: '#64748b',
};

function StatusPill({ status }: { status: 'ok' | 'error' | 'unset' }) {
  const color = status === 'ok' ? '#10b981' : status === 'error' ? '#ef4444' : '#64748b';
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '1px 6px',
        fontSize: 10,
        textTransform: 'uppercase',
        borderRadius: 3,
        background: color,
        color: 'white',
      }}
    >
      {status}
    </span>
  );
}

function SpanTable({ spans }: { spans: TraceSpan[] }) {
  if (spans.length === 0) {
    return <EmptyState title="No spans" description="This trace has no recorded spans." icon="🔍" />;
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--color-border, #334155)' }}>
            <th style={{ textAlign: 'left', padding: '8px 4px' }}>Span</th>
            <th style={{ textAlign: 'left', padding: '8px 4px' }}>Kind</th>
            <th style={{ textAlign: 'left', padding: '8px 4px' }}>Status</th>
            <th style={{ textAlign: 'right', padding: '8px 4px' }}>Duration</th>
            <th style={{ textAlign: 'right', padding: '8px 4px' }}>Tokens</th>
          </tr>
        </thead>
        <tbody>
          {spans.map((s) => (
            <tr key={s.spanId} style={{ borderBottom: '1px solid var(--color-border, #1f2937)' }}>
              <td style={{ padding: '6px 4px', fontFamily: 'monospace' }}>{s.name}</td>
              <td style={{ padding: '6px 4px' }}>
                <span style={{ color: KIND_COLOR[s.kind] ?? '#94a3b8' }}>{s.kind}</span>
              </td>
              <td style={{ padding: '6px 4px' }}>
                <StatusPill status={s.status} />
              </td>
              <td style={{ padding: '6px 4px', textAlign: 'right' }}>
                {typeof s.durationMs === 'number' ? `${s.durationMs.toFixed(1)}ms` : '—'}
              </td>
              <td style={{ padding: '6px 4px', textAlign: 'right', color: 'var(--color-text-muted, #94a3b8)' }}>
                {typeof s.inputTokens === 'number' || typeof s.outputTokens === 'number'
                  ? `${s.inputTokens ?? 0}/${s.outputTokens ?? 0}`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TraceDetail({ traceId }: { traceId: string }) {
  const { data: trace, isLoading: sumLoading, error: sumErr } = useTrace(traceId);
  const { data: spans = [], isLoading: spansLoading, error: spansErr } = useTraceSpans(traceId);

  if (sumLoading || spansLoading) return <Skeleton width="100%" height={400} borderRadius="12px" />;
  if (sumErr) return <Banner variant="error">Failed to load trace: {(sumErr as Error).message}</Banner>;
  if (spansErr) return <Banner variant="error">Failed to load spans: {(spansErr as Error).message}</Banner>;
  if (!trace) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <Stat label="Trace ID" value={<code>{trace.traceId.slice(0, 16)}…</code>} />
        <Stat label="Spans" value={String(trace.spanCount)} />
        <Stat label="Errors" value={String(trace.errorCount)} tone={trace.errorCount > 0 ? 'danger' : undefined} />
        {typeof trace.durationMs === 'number' && (
          <Stat label="Duration" value={`${trace.durationMs.toFixed(1)}ms`} />
        )}
        {typeof trace.inputTokens === 'number' && (
          <Stat label="Input tokens" value={String(trace.inputTokens)} />
        )}
        {typeof trace.outputTokens === 'number' && (
          <Stat label="Output tokens" value={String(trace.outputTokens)} />
        )}
      </div>
      <SpanTable spans={spans} />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'danger' }) {
  return (
    <div
      style={{
        padding: '8px 12px',
        borderRadius: 8,
        border: '1px solid var(--color-border, #334155)',
        minWidth: 100,
      }}
    >
      <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--color-text-muted, #94a3b8)' }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 500, color: tone === 'danger' ? 'var(--color-danger, #ef4444)' : 'inherit' }}>
        {value}
      </div>
    </div>
  );
}

export default function ObservabilityPage() {
  const { data: runs = [], isLoading: runsLoading } = useRuns();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 320px) 1fr', gap: 16, height: 'calc(100vh - 120px)' }}>
      <aside
        style={{
          borderRight: '1px solid var(--color-border, #334155)',
          paddingRight: 12,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
        }}
      >
        <h2 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--color-text-muted, #94a3b8)', marginBottom: 8 }}>
          Runs
        </h2>
        {runsLoading && [1, 2, 3].map((i) => <Skeleton key={i} width="100%" height={44} borderRadius="8px" />)}
        {!runsLoading && runs.length === 0 && (
          <EmptyState title="No runs" description="Launch a run to see traces." icon="▶" />
        )}
        {!runsLoading && runs.map((r) => (
          <button
            key={r.id}
            onClick={() => setSelectedRunId(r.id)}
            style={{
              textAlign: 'left',
              padding: '10px 12px',
              borderRadius: 8,
              border: '1px solid transparent',
              background: selectedRunId === r.id ? 'var(--color-surface-hover, rgba(255,255,255,0.05))' : 'transparent',
              cursor: 'pointer',
              color: 'inherit',
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 500 }}>{r.title ?? r.id.slice(0, 8)}</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted, #94a3b8)' }}>
              {r.id.slice(0, 8)} · {r.status}
            </div>
          </button>
        ))}
      </aside>

      <main style={{ overflowY: 'auto', paddingRight: 4 }}>
        {selectedRunId ? (
          <TraceDetail traceId={selectedRunId} />
        ) : (
          <EmptyState
            title="Select a run"
            description="Pick a run from the sidebar to see its OpenTelemetry trace, aggregated stats, and per-span breakdown."
            icon="📊"
          />
        )}
      </main>
    </div>
  );
}
