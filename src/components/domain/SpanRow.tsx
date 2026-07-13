'use client';
import React from 'react';
import type { Span } from '@/lib/schemas/trace';
import { useTraceStore } from '@/features/trace/store';
import styles from './SpanRow.module.css';

const STATUS_CLASS: Record<Span['status'], string> = {
  ok: 'ok', error: 'error', unset: 'unset',
};

function flattenSpans(span: Span, depth = 0): { span: Span; depth: number }[] {
  return [{ span, depth }, ...span.children.flatMap((c) => flattenSpans(c, depth + 1))];
}

export interface SpanRowProps {
  span: Span;
  depth: number;
  traceStartTime: string;
  traceDurationMs: number;
}

export const SpanRow: React.FC<SpanRowProps> = ({ span, depth, traceStartTime, traceDurationMs }) => {
  const { expandedSpanIds, selectedSpanId, toggleSpan, selectSpan } = useTraceStore();
  const isExpanded = expandedSpanIds.has(span.spanId);
  const isSelected = selectedSpanId === span.spanId;
  const hasChildren = span.children.length > 0;

  const startOffset = new Date(span.startTime).getTime() - new Date(traceStartTime).getTime();
  const leftPct = traceDurationMs > 0 ? (startOffset / traceDurationMs) * 100 : 0;
  const widthPct = traceDurationMs > 0 && span.durationMs != null
    ? Math.max(0.5, (span.durationMs / traceDurationMs) * 100)
    : 1;

  return (
    <>
      <tr
        className={[styles.row, isSelected ? styles['row--selected'] : ''].filter(Boolean).join(' ')}
        onClick={() => selectSpan(span.spanId)}
        role="row"
        aria-selected={isSelected}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && selectSpan(span.spanId)}
      >
        {/* Name */}
        <td className={styles.nameCell} style={{ paddingLeft: `${depth * 16 + 8}px` }}>
          {hasChildren && (
            <button
              className={styles.expandBtn}
              onClick={(e) => { e.stopPropagation(); toggleSpan(span.spanId); }}
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
              aria-expanded={isExpanded}
            >
              {isExpanded ? '▾' : '▸'}
            </button>
          )}
          <span className={styles.spanName}>{span.name}</span>
        </td>

        {/* Status */}
        <td>
          <span className={[styles.statusBadge, styles[`statusBadge--${STATUS_CLASS[span.status]}`]].join(' ')}>
            {span.status}
          </span>
        </td>

        {/* Duration */}
        <td className={styles.durationCell}>
          {span.durationMs != null ? `${span.durationMs.toFixed(1)}ms` : '—'}
        </td>

        {/* Waterfall */}
        <td className={styles.waterfallCell}>
          <div className={styles.waterfallTrack}>
            <div
              className={[styles.waterfallBar, span.status === 'error' ? styles['waterfallBar--error'] : ''].filter(Boolean).join(' ')}
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            />
          </div>
        </td>
      </tr>

      {/* Render children if expanded */}
      {isExpanded && span.children.map((child) => (
        <SpanRow
          key={child.spanId}
          span={child}
          depth={depth + 1}
          traceStartTime={traceStartTime}
          traceDurationMs={traceDurationMs}
        />
      ))}
    </>
  );
};
