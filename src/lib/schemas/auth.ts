import { z } from 'zod';

export const RoleSchema = z.enum(['admin', 'developer', 'viewer']);
export type Role = z.infer<typeof RoleSchema>;

/**
 * Allowlisted domains for OAuth avatar URLs.
 * Prevents SSRF and user-tracking pixel injection via crafted OAuth tokens.
 */
const AVATAR_ALLOWED_HOSTNAMES = [
  'avatars.githubusercontent.com',
  'lh3.googleusercontent.com',
  'secure.gravatar.com',
  'cdn.discordapp.com',
];

const safeAvatarUrl = z
  .string()
  .url()
  .refine(
    (url) => {
      try {
        const { hostname } = new URL(url);
        return AVATAR_ALLOWED_HOSTNAMES.some(
          (allowed) => hostname === allowed || hostname.endsWith('.' + allowed),
        );
      } catch {
        return false;
      }
    },
    { message: 'Avatar URL must be from an allowed provider' },
  )
  .optional();

export const SessionUserSchema = z.object({
  id:        z.string(),
  email:     z.string().email(),
  name:      z.string(),
  role:      RoleSchema,
  avatarUrl: safeAvatarUrl,
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
