import { z } from 'zod';

// SecretRef: metadata only — raw values NEVER in the UI
export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
  // Never includes the actual secret value
  // 'masked' indicates a value is set; 'unset' means no value stored
  valueStatus: z.enum(['masked', 'unset']),
  usedByWorkspaces: z.array(z.string()).optional(),
  usedByRuns: z.number().optional(),
});

export type SecretRef = z.infer<typeof SecretRefSchema>;

export const SecretListResponseSchema = z.object({
  secrets: z.array(SecretRefSchema),
  total: z.number(),
});

export type SecretListResponse = z.infer<typeof SecretListResponseSchema>;

export const CreateSecretRequestSchema = z.object({
  name: z.string().min(1).regex(/^[A-Z0-9_]+$/, 'Secret names must be UPPER_SNAKE_CASE'),
  value: z.string().min(1),
  description: z.string().optional(),
});

export type CreateSecretRequest = z.infer<typeof CreateSecretRequestSchema>;
