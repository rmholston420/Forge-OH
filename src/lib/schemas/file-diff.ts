import { z } from 'zod';

export const FileDiffSchema = z.object({
  path: z.string(),
  status: z.enum(['added', 'modified', 'deleted', 'renamed', 'untracked']),
  additions: z.number().int().min(0),
  deletions: z.number().int().min(0),
  original: z.string().nullable(),
  modified: z.string().nullable(),
  language: z.string().default('plaintext'),
  isBinary: z.boolean().default(false),
});

export type FileDiff = z.infer<typeof FileDiffSchema>;

export const FileDiffSummarySchema = FileDiffSchema.omit({ original: true, modified: true });
export type FileDiffSummary = z.infer<typeof FileDiffSummarySchema>;
