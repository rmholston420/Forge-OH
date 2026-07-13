import { z } from 'zod';

export const TerminalCommandSchema = z.object({
  id: z.string(),
  command: z.string(),
  output: z.string(),
  exitCode: z.number().int().nullable(),
  startedAt: z.string(),
  durationMs: z.number().nullable(),
});

export type TerminalCommand = z.infer<typeof TerminalCommandSchema>;
