import { z } from 'zod';

export const EventTypeSchema = z.enum([
  'message',
  'tool_call',
  'tool_result',
  'file_edit',
  'command_run',
  'browser_action',
  'plan_update',
  'approval_required',
  'status_change',
  'error',
  'run_failed',
  'run_succeeded',
]);

export const ToolEventSchema = z.object({
  id: z.string(),
  eventId: z.union([z.string(), z.number()]).optional(),
  type: EventTypeSchema,
  runId: z.string(),
  timestamp: z.string().datetime(),
  source: z.string().optional(),
  summary: z.string().optional(),
  payload: z.record(z.unknown()).optional(),
  raw: z.unknown().optional(),
});

export type ToolEvent = z.infer<typeof ToolEventSchema>;

export const EventListSchema = z.object({
  events: z.array(ToolEventSchema),
  total: z.number().int().nonnegative(),
  hasMore: z.boolean(),
  latestEventId: z.union([z.string(), z.number()]).optional(),
});

export type EventList = z.infer<typeof EventListSchema>;
