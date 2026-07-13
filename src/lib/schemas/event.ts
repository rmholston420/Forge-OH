import { z } from 'zod';

export const ToolEventTypeSchema = z.enum([
  'message',
  'think',
  'plan',
  'edit_file',
  'run_command',
  'browser_action',
  'read_file',
  'web_search',
  'error',
  'finish',
]);

export const ToolEventSchema = z.object({
  id: z.string(),
  runId: z.string(),
  type: ToolEventTypeSchema,
  timestamp: z.string(),
  summary: z.string(),
  raw: z.record(z.unknown()).optional(),
  source: z.enum(['agent', 'user', 'system']),
});

export type ToolEvent = z.infer<typeof ToolEventSchema>;
