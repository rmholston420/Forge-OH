import { z } from 'zod';

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run']);
export type SecretScope = z.infer<typeof SecretScopeSchema>;

export const SecretSchema = z.object({
  id:          z.string(),
  key:         z.string().regex(/^[A-Z_][A-Z0-9_]*$/, 'Must be UPPER_SNAKE_CASE'),
  scope:       SecretScopeSchema,
  workspaceId: z.string().optional(),
  maskedValue: z.string(),   // e.g. '****4f2a' — server never returns raw value
  createdAt:   z.string().datetime(),
  updatedAt:   z.string().datetime(),
  createdBy:   z.string(),
  tags:        z.array(z.string()).default([]),
});
export type Secret = z.infer<typeof SecretSchema>;

export const CreateSecretSchema = z.object({
  key:         z.string().regex(/^[A-Z_][A-Z0-9_]*$/, 'Must be UPPER_SNAKE_CASE'),
  value:       z.string().min(1, 'Value is required'),
  scope:       SecretScopeSchema.default('global'),
  workspaceId: z.string().optional(),
  tags:        z.array(z.string()).default([]),
});
export type CreateSecretRequest = z.infer<typeof CreateSecretSchema>;

export const RotateSecretSchema = z.object({
  newValue: z.string().min(1, 'New value is required'),
});
