import { z } from 'zod';

export const TraceSpanTypeSchema = z.enum(['llm', 'tool', 'workspace', 'browser', 'network', 'system']);
export type TraceSpanType = z.infer<typeof TraceSpanTypeSchema>;

export const TraceSpanStatusSchema = z.enum(['ok', 'warning', 'error', 'unset']);
export type TraceSpanStatus = z.infer<typeof TraceSpanStatusSchema>;

export interface TraceSpan {
  id: string;
  spanId?: string;
  traceId?: string;
  runId: string;
  parentId: string | null;
  parentSpanId?: string | null;
  name: string;
  type: TraceSpanType;
  status: TraceSpanStatus;
  startedAt: string;
  startTime?: string;
  endedAt?: string;
  endTime?: string;
  durationMs?: number;
  attributes?: Record<string, unknown>;
  events?: Array<Record<string, unknown>>;
  children: TraceSpan[];
}

export const TraceSpanSchema: z.ZodType<TraceSpan> = z.lazy(() =>
  z.object({
    id: z.string().min(1),
    spanId: z.string().min(1).optional(),
    traceId: z.string().min(1).optional(),
    runId: z.string().min(1).default('unknown-run'),
    parentId: z.string().nullable().default(null),
    parentSpanId: z.string().nullable().optional(),
    name: z.string().min(1),
    type: TraceSpanTypeSchema.default('system'),
    status: TraceSpanStatusSchema.default('unset'),
    startedAt: z.string(),
    startTime: z.string().optional(),
    endedAt: z.string().optional(),
    endTime: z.string().optional(),
    durationMs: z.number().optional(),
    attributes: z.record(z.string(), z.unknown()).optional(),
    events: z.array(z.record(z.string(), z.unknown())).optional(),
    children: z.array(TraceSpanSchema).default([]),
  })
);

export const SpanSchema = TraceSpanSchema;
export const TraceSpanRowSchema = TraceSpanSchema;

export const TraceSchema = z.object({
  traceId: z.string().min(1),
  runId: z.string().optional(),
  spans: z.array(TraceSpanSchema).default([]),
  rootSpan: TraceSpanSchema.optional(),
  startTime: z.string().optional(),
  totalSpans: z.number().int().min(0).optional(),
});

export type Span = TraceSpan;
export type Trace = z.infer<typeof TraceSchema>;
