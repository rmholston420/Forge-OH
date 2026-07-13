/**
 * Unit tests: src/lib/schemas/auth.ts
 *
 * Covers LoginRequestSchema, SessionUserSchema, safeAvatarUrl allowlist,
 * and the RoleSchema enum — all added/hardened in the last fix pass.
 */
import { describe, it, expect } from 'vitest';
import {
  LoginRequestSchema,
  SessionUserSchema,
  RoleSchema,
  AuthErrorSchema,
} from '@/lib/schemas/auth';

// ---------------------------------------------------------------------------
// LoginRequestSchema
// ---------------------------------------------------------------------------
describe('LoginRequestSchema', () => {
  it('accepts valid email and 8-char password', () => {
    expect(LoginRequestSchema.safeParse({
      email: 'admin@forge.dev', password: 'password'
    }).success).toBe(true);
  });

  it('rejects invalid email format', () => {
    expect(LoginRequestSchema.safeParse({
      email: 'not-an-email', password: 'password123'
    }).success).toBe(false);
  });

  it('rejects password shorter than 8 characters', () => {
    expect(LoginRequestSchema.safeParse({
      email: 'admin@forge.dev', password: 'short'
    }).success).toBe(false);
  });

  it('rejects exactly 7-character password', () => {
    expect(LoginRequestSchema.safeParse({
      email: 'admin@forge.dev', password: '1234567'
    }).success).toBe(false);
  });

  it('accepts exactly 8-character password', () => {
    expect(LoginRequestSchema.safeParse({
      email: 'admin@forge.dev', password: '12345678'
    }).success).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// RoleSchema
// ---------------------------------------------------------------------------
describe('RoleSchema', () => {
  it.each(['admin', 'developer', 'viewer'])('accepts valid role: %s', (role) => {
    expect(RoleSchema.safeParse(role).success).toBe(true);
  });

  it('rejects unknown role', () => {
    expect(RoleSchema.safeParse('superuser').success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// SessionUserSchema — safeAvatarUrl allowlist
// ---------------------------------------------------------------------------
const baseUser = { id: '1', email: 'a@b.com', name: 'A', role: 'admin' as const };

describe('SessionUserSchema — avatarUrl allowlist', () => {
  it('accepts absent avatarUrl', () => {
    expect(SessionUserSchema.safeParse(baseUser).success).toBe(true);
  });

  it('accepts GitHub avatars CDN', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://avatars.githubusercontent.com/u/1?v=4'
    }).success).toBe(true);
  });

  it('accepts Google user content CDN', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://lh3.googleusercontent.com/a/photo.jpg'
    }).success).toBe(true);
  });

  it('accepts Gravatar CDN', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://secure.gravatar.com/avatar/abc123'
    }).success).toBe(true);
  });

  it('accepts Discord CDN', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://cdn.discordapp.com/avatars/123/abc.png'
    }).success).toBe(true);
  });

  it('rejects arbitrary external URL (SSRF vector)', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://evil.com/tracking.gif'
    }).success).toBe(false);
  });

  it('rejects localhost URL', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'http://localhost:9000/avatar.png'
    }).success).toBe(false);
  });

  it('rejects a subdomain spoofing an allowed host', () => {
    expect(SessionUserSchema.safeParse({
      ...baseUser, avatarUrl: 'https://attacker.com/avatars.githubusercontent.com/u/1'
    }).success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// AuthErrorSchema
// ---------------------------------------------------------------------------
describe('AuthErrorSchema', () => {
  it('accepts valid error codes', () => {
    for (const code of ['invalid_credentials', 'account_locked', 'server_error'] as const) {
      expect(AuthErrorSchema.safeParse({ code, message: 'err' }).success).toBe(true);
    }
  });

  it('rejects unknown error code', () => {
    expect(AuthErrorSchema.safeParse({ code: 'unknown_code', message: 'err' }).success).toBe(false);
  });
});
