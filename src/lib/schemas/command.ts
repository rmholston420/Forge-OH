import { z } from 'zod';

export const CommandRiskLevelSchema = z.enum(['low', 'medium', 'high', 'critical']);
export type CommandRiskLevel = z.infer<typeof CommandRiskLevelSchema>;

export const CommandExecutionSchema = z.object({
  id: z.string(),
  runId: z.string().optional(),
  command: z.string(),
  cwd: z.string().optional(),
  exitCode: z.number().nullable(),
  durationMs: z.number().nullable(),
  riskLevel: CommandRiskLevelSchema,
  stdoutPreview: z.string().optional(),
  stderrPreview: z.string().optional(),
  // Output may be truncated — fetch full output via /api/runs/:id/commands/:commandId/output
  outputTruncated: z.boolean().optional(),
  startTime: z.string(),
  endTime: z.string().nullable(),
});

export type CommandExecution = z.infer<typeof CommandExecutionSchema>;

export const CommandListResponseSchema = z.object({
  commands: z.array(CommandExecutionSchema),
  total: z.number(),
});

export type CommandListResponse = z.infer<typeof CommandListResponseSchema>;
