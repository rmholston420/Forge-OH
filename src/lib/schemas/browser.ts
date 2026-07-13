import { z } from 'zod';

export const BrowserSessionStatusSchema = z.enum([
  'idle',
  'navigating',
  'interacting',
  'extracting',
  'failed',
]);

export const BrowserSessionSchema = z.object({
  id: z.string(),
  runId: z.string(),
  status: BrowserSessionStatusSchema,
  currentUrl: z.string().optional(),
  screenshotBase64: z.string().optional(),
  steps: z.array(z.object({
    id: z.string(),
    type: z.enum(['navigate', 'click', 'type', 'scroll', 'extract']),
    description: z.string(),
    timestamp: z.string(),
  })),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type BrowserSession = z.infer<typeof BrowserSessionSchema>;
