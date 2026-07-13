import { z } from 'zod';

export const RoleSchema = z.enum(['admin', 'developer', 'editor', 'viewer']);
export type Role = z.infer<typeof RoleSchema>;

export const AvatarUrlSchema = z
  .string()
  .url()
  .refine((u) => {
    try {
      const url = new URL(u);
      if (url.protocol !== 'https:') return false;
      return [
        'avatars.githubusercontent.com',
        'lh3.googleusercontent.com',
        'www.gravatar.com',
        'cdn.discordapp.com',
      ].includes(url.hostname);
    } catch {
      return false;
    }
  })
  .optional();

export const SessionUserSchema = z.object({
  id: z.string(),
  email: z.string().email(),
  name: z.string(),
  role: RoleSchema,
  avatarUrl: AvatarUrlSchema.optional(),
});

export type SessionUser = z.infer<typeof SessionUserSchema>;

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const AuthErrorSchema = z.object({
  message: z.string(),
  code: z.string().optional(),
});

export type AuthError = z.infer<typeof AuthErrorSchema>;
