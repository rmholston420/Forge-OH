import { z } from 'zod';

export const SecretScopeSchema = z.enum(['global', 'workspace', 'run']);
export type SecretScope = z.infer<typeof SecretScopeSchema>;

export const SecretRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  maskedValue: z.string(),
  scope: SecretScopeSchema,
  scopeId: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type SecretRef = z.infer<typeof SecretRefSchema>;
// Raw values NEVER in this schema — BFF redacts all raw values
