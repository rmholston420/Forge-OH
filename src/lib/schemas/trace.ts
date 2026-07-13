import { z } from 'zod';

export const TraceSpanKindSchema = z.enum([
  'llm',
  'tool',
  'workspace',
  'browser',
  'network',
  'internal',
]);

export const TraceSpanSchema = z.object({
  spanId: z.string(),
  traceId: z.string(),
  parentSpanId: z.string().nullable().optional(),
  runId: z.string(),
  kind: TraceSpanKindSchema,
  name: z.string(),
  startTime: z.string().datetime(),
  endTime: z.string().datetime().optional(),
  durationMs: z.number().nonnegative().optional(),
  status: z.enum(['ok', 'error', 'unset']),
  attributes: z.record(z.unknown()).optional(),
  events: z.array(z.record(z.unknown())).optional(),
});

export type TraceSpan = z.infer<typeof TraceSpanSchema>;

export const TraceListSchema = z.object({
  spans: z.array(TraceSpanSchema),
  total: z.number().int().nonnegative(),
});

export type TraceList = z.infer<typeof TraceListSchema>;
