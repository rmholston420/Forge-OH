import { z } from 'zod';

export const BrowserActionTypeSchema = z.enum([
  'navigate',
  'click',
  'type',
  'scroll',
  'screenshot',
  'wait',
  'close',
]).or(z.string());

export const BrowserStepSchema = z.object({
  stepId: z.string(),
  actionType: BrowserActionTypeSchema,
  url: z.string().optional(),
  selector: z.string().optional(),
  value: z.string().optional(),
  screenshotUrl: z.string().url().optional(),
  timestamp: z.string(),
  success: z.boolean(),
  errorMessage: z.string().optional(),
});

export type BrowserStep = z.infer<typeof BrowserStepSchema>;

export const BrowserSessionSchema = z.object({
  sessionId: z.string(),
  runId: z.string(),
  currentUrl: z.string().optional(),
  title: z.string().optional(),
  steps: z.array(BrowserStepSchema),
  startTime: z.string(),
  endTime: z.string().nullable(),
  viewportWidth: z.number().optional(),
  viewportHeight: z.number().optional(),
});

export type BrowserSession = z.infer<typeof BrowserSessionSchema>;

export const BrowserSessionListResponseSchema = z.object({
  sessions: z.array(BrowserSessionSchema),
  total: z.number(),
});

export type BrowserSessionListResponse = z.infer<typeof BrowserSessionListResponseSchema>;

// Individual frame/screenshot captured during a browser step.
export const BrowserFrameSchema = z.object({
  id: z.string(),
  runId: z.string().optional(),
  timestamp: z.string(),
  seq: z.number().default(0),
  url: z.string().optional(),
  screenshotUrl: z.string().optional(),
  domSnapshotUrl: z.string().optional(),
  action: z.string().default('navigate'),
  selector: z.string().optional(),
  error: z.string().optional(),
  boundingBox: z.object({
    x: z.number(),
    y: z.number(),
    width: z.number(),
    height: z.number(),
  }).optional(),
});

export type BrowserFrame = z.infer<typeof BrowserFrameSchema>;
