import { z } from 'zod';

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run']);

export const SecretSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(120),
  scope: SecretScopeSchema,
  scopeId: z.string().nullable().default(null),  // workspaceId or runId when scoped
  description: z.string().nullable().default(null),
  masked: z.literal(true).default(true),          // value is NEVER returned from API
  lastRotatedAt: z.string().nullable().default(null),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export const UpsertSecretSchema = z.object({
  name: z.string().min(1).max(120),
  value: z.string().min(1),
  scope: SecretScopeSchema.default('global'),
  scopeId: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
});

export type Secret = z.infer<typeof SecretSchema>;
export type SecretScope = z.infer<typeof SecretScopeSchema>;
export type UpsertSecret = z.infer<typeof UpsertSecretSchema>;
