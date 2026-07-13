import { z } from 'zod';

export const ArtifactTypeSchema = z.enum([
  'file_change',
  'patch',
  'screenshot',
  'report',
  'log',
  'archive',
  'other',
]);
export type ArtifactType = z.infer<typeof ArtifactTypeSchema>;

export const ArtifactSchema = z.object({
  id: z.string(),
  runId: z.string(),
  type: ArtifactTypeSchema,
  name: z.string(),
  path: z.string().optional(),
  mimeType: z.string().optional(),
  sizeBytes: z.number().optional(),
  createdAt: z.string().datetime(),
  downloadUrl: z.string().url().optional(),
  previewUrl: z.string().url().optional(),
  isBinary: z.boolean().optional(),
});

export type Artifact = z.infer<typeof ArtifactSchema>;

export const ArtifactListResponseSchema = z.object({
  artifacts: z.array(ArtifactSchema),
  total: z.number(),
  groupedByType: z.record(z.array(ArtifactSchema)).optional(),
});

export type ArtifactListResponse = z.infer<typeof ArtifactListResponseSchema>;
