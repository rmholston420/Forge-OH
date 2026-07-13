import { z } from 'zod';

export const SpanTypeSchema = z.enum(['llm', 'tool', 'workspace', 'browser', 'network', 'system']);
export type SpanType = z.infer<typeof SpanTypeSchema>;

export const TraceSpanSchema = z.object({
  id: z.string(),
  runId: z.string(),
  parentId: z.string().nullable(),
  type: SpanTypeSchema,
  name: z.string(),
  startTime: z.string(),
  endTime: z.string().nullable(),
  durationMs: z.number().nullable(),
  status: z.enum(['ok', 'error', 'unset']),
  attributes: z.record(z.unknown()).optional(),
  linkedEventId: z.string().nullable(),
});

export type TraceSpan = z.infer<typeof TraceSpanSchema>;
