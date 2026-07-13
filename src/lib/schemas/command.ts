import { z } from 'zod';

export const CommandRiskLevelSchema = z.enum(['low', 'medium', 'high', 'critical']);

export const CommandExecutionSchema = z.object({
  id: z.string(),
  runId: z.string(),
  command: z.string(),
  cwd: z.string().optional(),
  exitCode: z.number().int().nullable(),
  durationMs: z.number().nonnegative().nullable(),
  riskLevel: CommandRiskLevelSchema,
  stdoutPreview: z.string().optional(),
  stderrPreview: z.string().optional(),
  // Full output fetched separately via /api/runs/:id/commands/:commandId/output
  // to avoid bloating list responses
  startedAt: z.string().datetime(),
  finishedAt: z.string().datetime().nullable().optional(),
  secretsMasked: z.boolean().optional(),
});

export type CommandExecution = z.infer<typeof CommandExecutionSchema>;

export const CommandListSchema = z.object({
  commands: z.array(CommandExecutionSchema),
  total: z.number().int().nonnegative(),
});

export type CommandList = z.infer<typeof CommandListSchema>;
