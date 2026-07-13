/**
 * Edge-case tests for auth schemas — supplements auth-schemas.test.ts.
 * Focuses on the avatarUrl allowlist fix and SessionUser shape.
 */
import { describe, it, expect } from 'vitest';
import { SessionUserSchema, AvatarUrlSchema } from '../../lib/schemas/auth';

// ---------------------------------------------------------------------------
// AvatarUrl allowlist (final-pass fix)
// ---------------------------------------------------------------------------
describe('AvatarUrlSchema — allowlist', () => {
  it('accepts GitHub avatar URL', () => {
    expect(AvatarUrlSchema.safeParse('https://avatars.githubusercontent.com/u/12345').success).toBe(true);
  });

  it('accepts Google avatar URL', () => {
    expect(AvatarUrlSchema.safeParse('https://lh3.googleusercontent.com/a/abc').success).toBe(true);
  });

  it('accepts Gravatar URL', () => {
    expect(AvatarUrlSchema.safeParse('https://www.gravatar.com/avatar/abc123').success).toBe(true);
  });

  it('accepts Discord CDN URL', () => {
    expect(AvatarUrlSchema.safeParse('https://cdn.discordapp.com/avatars/123/abc.png').success).toBe(true);
  });

  it('rejects arbitrary external URL', () => {
    expect(AvatarUrlSchema.safeParse('https://evil.com/avatar.png').success).toBe(false);
  });

  it('rejects http (non-https) GitHub URL', () => {
    expect(AvatarUrlSchema.safeParse('http://avatars.githubusercontent.com/u/1').success).toBe(false);
  });

  it('accepts undefined (field is optional)', () => {
    expect(AvatarUrlSchema.safeParse(undefined).success).toBe(true);
  });

  it('rejects empty string', () => {
    expect(AvatarUrlSchema.safeParse('').success).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// SessionUser shape
// ---------------------------------------------------------------------------
describe('SessionUserSchema', () => {
  const base = {
    id: 'user-001',
    name: 'Alice',
    email: 'alice@example.com',
    role: 'admin',
  };

  it('accepts a valid admin user', () => {
    expect(SessionUserSchema.safeParse(base).success).toBe(true);
  });

  it('accepts editor role', () => {
    expect(SessionUserSchema.safeParse({ ...base, role: 'editor' }).success).toBe(true);
  });

  it('accepts viewer role', () => {
    expect(SessionUserSchema.safeParse({ ...base, role: 'viewer' }).success).toBe(true);
  });

  it('rejects unknown role', () => {
    expect(SessionUserSchema.safeParse({ ...base, role: 'superuser' }).success).toBe(false);
  });

  it('accepts user with valid GitHub avatarUrl', () => {
    const user = { ...base, avatarUrl: 'https://avatars.githubusercontent.com/u/99' };
    expect(SessionUserSchema.safeParse(user).success).toBe(true);
  });

  it('rejects user with off-list avatarUrl', () => {
    const user = { ...base, avatarUrl: 'https://attacker.io/img.png' };
    expect(SessionUserSchema.safeParse(user).success).toBe(false);
  });

  it('accepts user with no avatarUrl', () => {
    expect(SessionUserSchema.safeParse(base).success).toBe(true);
  });

  it('rejects missing required email', () => {
    const { email: _, ...noEmail } = base;
    expect(SessionUserSchema.safeParse(noEmail).success).toBe(false);
  });

  it('rejects malformed email', () => {
    expect(SessionUserSchema.safeParse({ ...base, email: 'not-an-email' }).success).toBe(false);
  });
});
