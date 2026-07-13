import { z } from 'zod';

export const EventTypeSchema = z.enum([
  'message',
  'action',
  'observation',
  'plan_update',
  'file_change',
  'command_start',
  'command_end',
  'browser_action',
  'browser_observation',
  'approval_required',
  'approval_granted',
  'approval_rejected',
  'error',
  'run_started',
  'run_paused',
  'run_resumed',
  'run_stopped',
  'run_succeeded',
  'run_failed',
  'status',
]).or(z.string());

export type EventType = z.infer<typeof EventTypeSchema>;

export const ToolEventSchema = z.object({
  id: z.union([z.string(), z.number()]),
  eventId: z.union([z.string(), z.number()]).optional(),
  type: EventTypeSchema,
  timestamp: z.string(),
  runId: z.string().optional(),
  source: z.string().optional(),
  summary: z.string().optional(),
  payload: z.record(z.unknown()).optional(),
  rawPayload: z.record(z.unknown()).optional(),
  raw: z.unknown().optional(),
});

export type ToolEvent = z.infer<typeof ToolEventSchema>;

export const EventListResponseSchema = z.object({
  events: z.array(ToolEventSchema),
  total: z.number().optional(),
  latestEventId: z.union([z.string(), z.number()]).optional(),
});

export type EventListResponse = z.infer<typeof EventListResponseSchema>;
