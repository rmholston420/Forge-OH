import { z } from 'zod';

export const SpanStatusSchema = z.enum(['ok', 'error', 'unset']);

export const SpanSchema = z.object({
  spanId: z.string(),
  traceId: z.string(),
  parentSpanId: z.string().nullable().default(null),
  name: z.string(),
  status: SpanStatusSchema,
  startTime: z.string(),
  endTime: z.string().nullable().default(null),
  durationMs: z.number().nullable().default(null),
  attributes: z.record(z.unknown()).default({}),
  events: z.array(z.object({
    name: z.string(),
    timestamp: z.string(),
    attributes: z.record(z.unknown()).default({}),
  })).default([]),
  children: z.array(z.lazy((): z.ZodType => SpanSchema)).default([]),
});

export const TraceSchema = z.object({
  traceId: z.string(),
  runId: z.string(),
  rootSpan: SpanSchema,
  totalSpans: z.number().int(),
  durationMs: z.number().nullable().default(null),
  startTime: z.string(),
  endTime: z.string().nullable().default(null),
  hasErrors: z.boolean().default(false),
});

export type Span = z.infer<typeof SpanSchema>;
export type Trace = z.infer<typeof TraceSchema>;
