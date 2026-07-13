import { z } from 'zod';

export const TraceSpanKindSchema = z.enum(['llm', 'tool', 'workspace', 'browser', 'network', 'internal']);
export type TraceSpanKind = z.infer<typeof TraceSpanKindSchema>;

export const TraceSpanSchema = z.object({
  spanId: z.string(),
  traceId: z.string(),
  parentSpanId: z.string().nullable(),
  name: z.string(),
  kind: TraceSpanKindSchema,
  startTime: z.string(),
  endTime: z.string().nullable(),
  durationMs: z.number().nullable(),
  status: z.enum(['ok', 'error', 'unset']),
  attributes: z.record(z.unknown()).optional(),
  events: z.array(z.object({
    name: z.string(),
    timestamp: z.string(),
    attributes: z.record(z.unknown()).optional(),
  })).optional(),
  runId: z.string().optional(),
  inputTokens: z.number().optional(),
  outputTokens: z.number().optional(),
  estimatedCostUsd: z.number().optional(),
});

export type TraceSpan = z.infer<typeof TraceSpanSchema>;

export const TraceListResponseSchema = z.object({
  spans: z.array(TraceSpanSchema),
  total: z.number(),
});

export type TraceListResponse = z.infer<typeof TraceListResponseSchema>;
