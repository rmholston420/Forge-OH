'use client';
import { useTraceSpans } from '@/features/trace/hooks';
import { useTraceStore } from '@/features/trace/store';
import { SpanRow } from '@/components/domain/SpanRow';

interface Props { runId: string; }

export function TraceTab({ runId }: Props) {
  const { data: spans = [], isLoading } = useTraceSpans(runId);
  const { selectedSpanId, setSelectedSpanId } = useTraceStore();

  const roots = spans.filter((s) => !s.parentId);

  if (isLoading) {
    return (
      <div className="trace-skeleton" aria-busy="true" aria-label="Loading trace">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton skeleton-text"
               style={{ width: `${80 - i * 8}%`, marginLeft: `${i * 12}px` }} />
        ))}
      </div>
    );
  }

  if (!roots.length) {
    return (
      <div className="empty-state">
        <p>No trace spans recorded for this run.</p>
      </div>
    );
  }

  return (
    <div className="trace-tab">
      <div className="trace-header">
        <span className="trace-span-count">{spans.length} span{spans.length !== 1 ? 's' : ''}</span>
      </div>
      <ul role="tree" aria-label="Trace spans" className="trace-tree">
        {roots.map((span) => (
          <SpanRow
            key={span.id}
            span={span}
           
            depth={0}
            traceStartTime={span.startedAt || new Date().toISOString()}
            traceDurationMs={span.durationMs || 1}
           
           
          />
        ))}
      </ul>
    </div>
  );
}

export default TraceTab;
