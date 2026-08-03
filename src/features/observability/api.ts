/**
 * src/features/observability/api.ts
 *
 * BFF calls for the observability page (traces + spans).
 */
import { bffGet } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import type { RunMetrics } from '@/lib/schemas/metric';
import type { TraceSummary, TraceSpan } from '@/lib/schemas/trace';

export async function fetchRunMetrics(runId: string): Promise<RunMetrics> {
  const res = await bffGet<{ data: RunMetrics }>(`/api/runs/${runId}/metrics`);
  return unwrap(res).data;
}

export async function fetchAllTraces(): Promise<TraceSummary[]> {
  const res = await bffGet<{ data: TraceSummary[] }>(ENDPOINTS.OBSERVABILITY.traces());
  return unwrap(res).data ?? [];
}

export async function fetchTracesForRun(runId: string): Promise<TraceSummary[]> {
  const res = await bffGet<{ data: TraceSummary[] }>(ENDPOINTS.OBSERVABILITY.tracesForRun(runId));
  return unwrap(res).data ?? [];
}

export async function fetchTrace(traceId: string): Promise<TraceSummary> {
  const res = await bffGet<{ data: TraceSummary }>(ENDPOINTS.OBSERVABILITY.trace(traceId));
  return unwrap(res).data;
}

export async function fetchTraceSpans(traceId: string): Promise<TraceSpan[]> {
  const res = await bffGet<{ data: TraceSpan[] }>(ENDPOINTS.OBSERVABILITY.spans(traceId));
  return unwrap(res).data ?? [];
}
