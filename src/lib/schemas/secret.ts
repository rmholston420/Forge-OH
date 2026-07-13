import { z } from 'zod';

// Raw secret values NEVER appear in the UI or API responses.
// Only SecretRef metadata is returned.
export const SecretTypeSchema = z.enum([
  'api_key',
  'oauth_token',
  'ssh_key',
  'env_var',
  'certificate',
  'other',
]);

export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: SecretTypeSchema,
  description: z.string().optional(),
  lastRotatedAt: z.string().datetime().nullable().optional(),
  createdAt: z.string().datetime(),
  // Raw value is intentionally absent — never included in API responses
});

export type SecretRef = z.infer<typeof SecretRefSchema>;

export const SecretRefListSchema = z.array(SecretRefSchema);
export type SecretRefList = z.infer<typeof SecretRefListSchema>;

export const CreateSecretRequestSchema = z.object({
  name: z.string().min(1),
  type: SecretTypeSchema,
  value: z.string().min(1),
  description: z.string().optional(),
});

export type CreateSecretRequest = z.infer<typeof CreateSecretRequestSchema>;
