import { z } from 'zod';

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run']);
export const SecretProviderSchema = z.enum(['env', 'vault', 'k8s-secret', 'plaintext']);

export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(100),
  scope: SecretScopeSchema,
  provider: SecretProviderSchema,
  maskedPreview: z.string().max(16), // e.g. '••••••••' — NEVER the real value
  createdAt: z.string().datetime({ offset: true }),
  updatedAt: z.string().datetime({ offset: true }),
  rotatedAt: z.string().datetime({ offset: true }).nullable().default(null),
  usedIn: z.array(z.string()).default([]), // run IDs that reference this secret
});

export const SecretRefListSchema = z.array(SecretRefSchema);

/** Write-only: value is sent to BFF, NEVER returned */
export const CreateSecretRequestSchema = z.object({
  name: z.string().min(1).max(100),
  scope: SecretScopeSchema,
  provider: SecretProviderSchema,
  value: z.string().min(1), // write-only field
});

export const RotateSecretResponseSchema = z.object({
  secretId: z.string(),
  status: z.literal('rotated'),
  rotatedAt: z.string().datetime({ offset: true }),
});

export type SecretRef = z.infer<typeof SecretRefSchema>;
export type SecretScope = z.infer<typeof SecretScopeSchema>;
export type SecretProvider = z.infer<typeof SecretProviderSchema>;
export type CreateSecretRequest = z.infer<typeof CreateSecretRequestSchema>;
export type RotateSecretResponse = z.infer<typeof RotateSecretResponseSchema>;
