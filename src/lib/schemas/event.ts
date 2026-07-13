import { z } from 'zod';

export const EventSchema = z.object({
  id: z.union([z.string(), z.number()]),
  eventId: z.union([z.string(), z.number()]).optional(),
  type: z.string(),
  timestamp: z.string(),
  runId: z.string().optional(),
  source: z.string().optional(),
  payload: z.record(z.string(), z.unknown()).or(z.object({}).passthrough()).optional(),
  rawPayload: z.record(z.string(), z.unknown()).or(z.object({}).passthrough()).optional(),
  summary: z.string().optional(),
  raw: z.unknown().optional(),
});

export const ToolEventSchema = EventSchema;
export type Event = z.infer<typeof EventSchema>;
export type RunEvent = Event;
export type ToolEvent = Event;
