import { z } from 'zod';

export const BrowserActionTypeSchema = z.enum([
  'navigate', 'click', 'type', 'scroll', 'screenshot',
  'wait', 'hover', 'select', 'keypress', 'back', 'forward',
]);

export const BrowserFrameSchema = z.object({
  id: z.string(),
  runId: z.string(),
  seq: z.number().int(),
  action: BrowserActionTypeSchema,
  url: z.string().nullable().default(null),
  screenshotUrl: z.string().nullable().default(null),
  selector: z.string().nullable().default(null),
  value: z.string().nullable().default(null),
  boundingBox: z.object({ x: z.number(), y: z.number(), width: z.number(), height: z.number() }).nullable().default(null),
  durationMs: z.number().nullable().default(null),
  error: z.string().nullable().default(null),
  timestamp: z.string(),
});

export type BrowserFrame = z.infer<typeof BrowserFrameSchema>;
export type BrowserActionType = z.infer<typeof BrowserActionTypeSchema>;


export const BrowserStateSchema = BrowserFrameSchema;
