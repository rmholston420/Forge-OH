import { z } from 'zod';

export const RoleSchema = z.enum(['admin', 'developer', 'editor', 'viewer']);
export type Role = z.infer<typeof RoleSchema>;

export const AvatarUrlSchema = z.string().url().or(z.string().startsWith('/')).optional();

export const SessionUserSchema = z.object({
  id: z.string(),
  name: z.string().optional(),
  email: z.string().optional(),
  role: RoleSchema.default('viewer'),
  avatarUrl: AvatarUrlSchema,
  bffToken: z.string().optional(),
});
export type SessionUser = z.infer<typeof SessionUserSchema>;

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const AuthErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
});
export type AuthError = z.infer<typeof AuthErrorSchema>;
