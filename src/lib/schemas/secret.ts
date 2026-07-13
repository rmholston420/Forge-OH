import { z } from 'zod';

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run', 'user', 'deployment']);
export type SecretScope = z.infer<typeof SecretScopeSchema>;

export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string().default(''),
  key: z.string().optional(),
  scope: SecretScopeSchema,
  scopeId: z.string().optional(),
});
export type SecretRef = z.infer<typeof SecretRefSchema>;

export const SecretMetadataSchema = z.object({
  description: z.string().optional(),
  tags: z.array(z.string()).default([]),
  inUse: z.boolean().default(false),
  usedIn: z.array(z.string()).default([]),
  lastRotatedAt: z.string().optional(),
  createdBy: z.string().optional(),
});
export type SecretMetadata = z.infer<typeof SecretMetadataSchema>;

export const SecretSchema = SecretRefSchema.extend({
  maskedValue: z.string(),
  updatedAt: z.string(),
  createdAt: z.string().optional(),
  rawValue: z.string().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).default([]),
  inUse: z.boolean().default(false),
  usedIn: z.array(z.string()).default([]),
  lastRotatedAt: z.string().optional(),
  createdBy: z.string().optional(),
});
export type Secret = z.infer<typeof SecretSchema>;

export const CreateSecretSchema = z.object({
  name: z.string().min(1).default(''),
  key: z.string().min(1).optional(),
  value: z.string().min(1),
  scope: SecretScopeSchema.default('global'),
  scopeId: z.string().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).default([]),
});
export type CreateSecret = z.infer<typeof CreateSecretSchema>;

export const UpsertSecretSchema = z.object({
  id: z.string().optional(),
  name: z.string().optional(),
  key: z.string().optional(),
  value: z.string().min(1).optional(),
  newValue: z.string().min(1).optional(),
  scope: SecretScopeSchema.optional(),
  scopeId: z.string().optional(),
  description: z.string().optional(),
  tags: z.array(z.string()).default([]),
});
export type UpsertSecret = z.infer<typeof UpsertSecretSchema>;

export const RotateSecretSchema = z.object({
  id: z.string(),
  newValue: z.string(),
});
export type RotateSecret = z.infer<typeof RotateSecretSchema>;
