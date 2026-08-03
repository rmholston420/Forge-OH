import { z } from 'zod';

export const TraceSpanKindSchema = z.enum(['llm', 'tool', 'workspace', 'browser', 'network', 'internal']);
export type TraceSpanKind = z.infer<typeof TraceSpanKindSchema>;

/**
 * Canonical TraceSpan shape. Matches what the BFF returns
 * (see bff/services/trace_reconstruction.py::build_spans).
 *
 * Legacy aliases (`id`, `parentId`, `startedAt`, `children`) are kept as
 * optional compat fields so existing UI code (SpanRow, TraceTab, SecurityTab)
 * that was designed against an older tree-shaped Span type still type-checks.
 * All new code should use the canonical fields.
 */
export const TraceSpanSchema = z.object({
  // Canonical fields (returned by BFF)
  spanId: z.string(),
  traceId: z.string(),
  parentSpanId: z.string().nullable(),
  name: z.string(),
  kind: TraceSpanKindSchema,
  startTime: z.string(),
  endTime: z.string().nullable(),
  durationMs: z.number().nullable(),
  status: z.enum(['ok', 'error', 'unset']),
  attributes: z.record(z.string(), z.unknown()).optional(),
  events: z.array(z.object({
    name: z.string(),
    timestamp: z.string(),
    attributes: z.record(z.string(), z.unknown()).optional(),
  })).optional(),
  runId: z.string().optional(),
  inputTokens: z.number().optional(),
  outputTokens: z.number().optional(),
  estimatedCostUsd: z.number().optional(),

  // Legacy compat aliases. `children` is always [] because BFF spans are
  // flat; kept so tree-recursion UI code still type-checks.
  id: z.string().optional(),
  parentId: z.string().nullable().optional(),
  startedAt: z.string().optional(),
  children: z.array(z.lazy((): any => TraceSpanSchema)).default([]),
});

export type TraceSpan = z.infer<typeof TraceSpanSchema>;

export const TraceListResponseSchema = z.object({
  spans: z.array(TraceSpanSchema),
  total: z.number(),
});

export type TraceListResponse = z.infer<typeof TraceListResponseSchema>;

export type Span = TraceSpan;

/**
 * Trace summary as returned by GET /api/observability/traces/{traceId}
 * (or /runs/{runId}/traces). Includes aggregated stats + embedded spans.
 */
export const TraceSummarySchema = z.object({
  traceId: z.string(),
  runId: z.string().optional(),
  spanCount: z.number(),
  startTime: z.string().optional(),
  endTime: z.string().optional(),
  durationMs: z.number().optional(),
  status: z.enum(['ok', 'error', 'unset']),
  errorCount: z.number(),
  inputTokens: z.number().optional(),
  outputTokens: z.number().optional(),
  spans: z.array(TraceSpanSchema).default([]),

  // Compat fields for older UI code (SecurityTab)
  totalSpans: z.number().optional(),
  rootSpan: TraceSpanSchema.optional(),
});

export type TraceSummary = z.infer<typeof TraceSummarySchema>;
