import { z } from 'zod';

export const BrowserActionTypeSchema = z.enum([
  'navigate',
  'click',
  'type',
  'scroll',
  'screenshot',
  'wait',
  'close',
]);

export const BrowserStepSchema = z.object({
  stepId: z.string(),
  action: BrowserActionTypeSchema,
  url: z.string().url().optional(),
  selector: z.string().optional(),
  value: z.string().optional(),
  screenshotUrl: z.string().url().optional(),
  timestamp: z.string().datetime(),
  durationMs: z.number().nonnegative().optional(),
  error: z.string().optional(),
});

export type BrowserStep = z.infer<typeof BrowserStepSchema>;

export const BrowserSessionSchema = z.object({
  id: z.string(),
  runId: z.string(),
  startUrl: z.string().url().optional(),
  currentUrl: z.string().url().optional(),
  viewportWidth: z.number().int().positive().optional(),
  viewportHeight: z.number().int().positive().optional(),
  steps: z.array(BrowserStepSchema),
  createdAt: z.string().datetime(),
});

export type BrowserSession = z.infer<typeof BrowserSessionSchema>;
