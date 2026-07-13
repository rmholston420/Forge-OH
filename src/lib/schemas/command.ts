import { z } from 'zod';

export const CommandRiskLevelSchema = z.enum(['low', 'medium', 'high', 'critical']);

export const CommandExecutionSchema = z.object({
  id: z.string(),
  runId: z.string(),
  text: z.string(),
  cwd: z.string(),
  exitCode: z.number().nullable(),
  durationMs: z.number().nullable(),
  riskLevel: CommandRiskLevelSchema,
  stdoutPreview: z.string().optional(),
  stderrPreview: z.string().optional(),
  startedAt: z.string(),
  finishedAt: z.string().nullable(),
});

export type CommandExecution = z.infer<typeof CommandExecutionSchema>;
