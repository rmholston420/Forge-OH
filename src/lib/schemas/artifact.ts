import { z } from 'zod';

export const ArtifactTypeSchema = z.enum([
  'patch',
  'file',
  'screenshot',
  'report',
  'download',
  'image',
  'video',
  'log',
]);

export const ArtifactSchema = z.object({
  id: z.string(),
  runId: z.string(),
  type: ArtifactTypeSchema,
  name: z.string(),
  mimeType: z.string(),
  sizeBytes: z.number().int().min(0),
  url: z.string().url(),
  previewUrl: z.string().url().nullable().default(null),
  createdAt: z.string(),
});

export type Artifact = z.infer<typeof ArtifactSchema>;
export type ArtifactType = z.infer<typeof ArtifactTypeSchema>;
