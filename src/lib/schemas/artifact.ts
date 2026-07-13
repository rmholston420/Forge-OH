import { z } from 'zod';

export const ArtifactTypeSchema = z.enum(['file', 'diff', 'patch', 'image', 'report', 'download']);
export type ArtifactType = z.infer<typeof ArtifactTypeSchema>;

export const ArtifactSchema = z.object({
  id: z.string(),
  runId: z.string(),
  type: ArtifactTypeSchema,
  name: z.string(),
  path: z.string().optional(),
  sizeBytes: z.number().optional(),
  mimeType: z.string().optional(),
  createdAt: z.string(),
  downloadUrl: z.string().optional(),
});

export type Artifact = z.infer<typeof ArtifactSchema>;
