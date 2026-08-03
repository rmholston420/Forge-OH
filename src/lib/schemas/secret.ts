import { z } from 'zod';

/**
 * Secret domain schemas.
 *
 * Canonical field name is `name` (matches BFF and agent-server).
 * `rawValue` is a create-time-only field — it MUST NEVER appear on
 * read-side schemas or hit the UI. Any code that displays a secret works
 * with `SecretSchema` (metadata only, includes `valueStatus`).
 */

// ---------------------------------------------------------------------------
// Scope
// ---------------------------------------------------------------------------

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run']);
export type SecretScope = z.infer<typeof SecretScopeSchema>;

// ---------------------------------------------------------------------------
// Read-side: SecretRef (list rows), Secret (full metadata)
// ---------------------------------------------------------------------------

export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string().optional(),
  valueStatus: z.enum(['masked', 'unset']).default('masked'),
  usedByWorkspaces: z.array(z.string()).optional(),
  usedByRuns: z.number().optional(),
});
export type SecretRef = z.infer<typeof SecretRefSchema>;

/**
 * Full Secret record for detail views. Includes scope and rotation timestamp
 * but never the raw value. Consumers: SecretRow, secrets/page.tsx.
 */
export const SecretSchema = z.object({
  id: z.string(),
  name: z.string().min(1),
  scope: SecretScopeSchema,
  description: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string().optional(),
  lastRotatedAt: z.string().optional(),
  valueStatus: z.enum(['masked', 'unset']).default('masked'),
}).strict();
export type Secret = z.infer<typeof SecretSchema>;

export const SecretMetadataSchema = SecretRefSchema;
export type SecretMetadata = SecretRef;

export const SecretListResponseSchema = z.object({
  secrets: z.array(SecretRefSchema),
  total: z.number(),
});
export type SecretListResponse = z.infer<typeof SecretListResponseSchema>;

// ---------------------------------------------------------------------------
// Write-side: Create, Upsert, Rotate
// ---------------------------------------------------------------------------

const NAME_PATTERN = /^[A-Z0-9_]+$/;
const NAME_MSG = 'Secret names must be UPPER_SNAKE_CASE';

export const CreateSecretSchema = z.object({
  name: z.string().min(1).regex(NAME_PATTERN, NAME_MSG),
  scope: SecretScopeSchema.default('global'),
  rawValue: z.string().min(1),
  description: z.string().optional(),
});
export type CreateSecret = z.infer<typeof CreateSecretSchema>;

// Legacy alias — matches the pre-Stage-7 request shape used by the BFF
// (name/value, not name/rawValue). Kept for backward compat.
export const CreateSecretRequestSchema = z.object({
  name: z.string().min(1).regex(NAME_PATTERN, NAME_MSG),
  value: z.string().min(1),
  description: z.string().optional(),
});
export type CreateSecretRequest = z.infer<typeof CreateSecretRequestSchema>;

export const UpsertSecretSchema = z.object({
  name: z.string().min(1).regex(NAME_PATTERN, NAME_MSG),
  value: z.string().min(1),
  scope: SecretScopeSchema.default('global'),
  description: z.string().optional(),
});
export type UpsertSecret = z.infer<typeof UpsertSecretSchema>;

export const RotateSecretSchema = z.object({
  newValue: z.string().min(1),
});
export type RotateSecret = z.infer<typeof RotateSecretSchema>;
