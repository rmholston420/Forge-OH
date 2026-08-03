import type { TraceSpan, TraceSummary } from '@/lib/schemas/trace';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

/**
 * Normalize a span: populate legacy compat aliases (`id`, `parentId`,
 * `startedAt`, `children`) so older UI code that reads them still works.
 * The BFF returns spans as a flat list — we always set `children: []`.
 */
function normalizeSpan(s: TraceSpan): TraceSpan {
  return {
    ...s,
    id: s.id ?? s.spanId,
    parentId: s.parentId ?? s.parentSpanId,
    startedAt: s.startedAt ?? s.startTime,
    children: s.children ?? [],
  };
}

export async function fetchTraceSpans(runId: string): Promise<TraceSpan[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/traces`);
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`fetchTraceSpans failed: ${res.status}`);
  const json = await res.json();
  const spans: TraceSpan[] = json?.data ?? [];
  return spans.map(normalizeSpan);
}

export async function fetchTrace(runId: string): Promise<TraceSummary | null> {
  const res = await fetch(`${BFF}/api/observability/traces/${runId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`fetchTrace failed: ${res.status}`);
  const json = await res.json();
  const data: TraceSummary | undefined = json?.data;
  if (!data) return null;
  const spans = (data.spans ?? []).map(normalizeSpan);
  return {
    ...data,
    spans,
    totalSpans: data.totalSpans ?? data.spanCount,
    rootSpan: data.rootSpan ?? spans[0],
  };
}
