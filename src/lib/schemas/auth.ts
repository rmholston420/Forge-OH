import { z } from 'zod';

export const RoleSchema = z.enum(['admin', 'developer', 'viewer']);
export type Role = z.infer<typeof RoleSchema>;

export const SessionUserSchema = z.object({
  id:        z.string(),
  email:     z.string().email(),
  name:      z.string(),
  role:      RoleSchema,
  avatarUrl: z.string().url().optional(),
});
export type SessionUser = z.infer<typeof SessionUserSchema>;

export const LoginRequestSchema = z.object({
  email:    z.string().email('Enter a valid email'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const AuthErrorSchema = z.object({
  code:    z.enum(['invalid_credentials', 'account_locked', 'server_error']),
  message: z.string(),
});
export type AuthError = z.infer<typeof AuthErrorSchema>;
