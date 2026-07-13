import { z } from 'zod';

export const ArtifactTypeSchema = z.enum([
  'file',
  'diff',
  'patch',
  'image',
  'report',
  'download',
  'log',
]);

export const ArtifactSchema = z.object({
  id: z.string(),
  runId: z.string(),
  type: ArtifactTypeSchema,
  name: z.string(),
  path: z.string().optional(),
  sizeBytes: z.number().int().nonnegative().optional(),
  mimeType: z.string().optional(),
  previewUrl: z.string().url().optional(),
  downloadUrl: z.string().url().optional(),
  createdAt: z.string().datetime(),
  meta: z.record(z.unknown()).optional(),
});

export type Artifact = z.infer<typeof ArtifactSchema>;

export const ArtifactListSchema = z.object({
  artifacts: z.array(ArtifactSchema),
  total: z.number().int().nonnegative(),
});

export type ArtifactList = z.infer<typeof ArtifactListSchema>;
