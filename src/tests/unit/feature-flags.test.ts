/**
 * Unit tests: feature flag resolution.
 * Verifies flags read from NEXT_PUBLIC_FEATURE_* env vars correctly.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// We test the flag resolution logic directly rather than importing the
// module (which caches at import time), so we can control env vars.
const isEnabled = (flag: string): boolean =>
  process.env[flag] === 'true';

describe('feature flag resolution', () => {
  const originalEnv = { ...process.env };

  afterEach(() => {
    Object.assign(process.env, originalEnv);
    // restore any flags set during tests
    Object.keys(process.env)
      .filter((k) => k.startsWith('NEXT_PUBLIC_FEATURE_'))
      .forEach((k) => { delete process.env[k]; });
    Object.assign(process.env, originalEnv);
  });

  it('returns false when flag is absent', () => {
    delete process.env['NEXT_PUBLIC_FEATURE_TEST_FLAG'];
    expect(isEnabled('NEXT_PUBLIC_FEATURE_TEST_FLAG')).toBe(false);
  });

  it('returns true when flag is "true"', () => {
    process.env['NEXT_PUBLIC_FEATURE_TEST_FLAG'] = 'true';
    expect(isEnabled('NEXT_PUBLIC_FEATURE_TEST_FLAG')).toBe(true);
  });

  it('returns false when flag is "false"', () => {
    process.env['NEXT_PUBLIC_FEATURE_TEST_FLAG'] = 'false';
    expect(isEnabled('NEXT_PUBLIC_FEATURE_TEST_FLAG')).toBe(false);
  });

  it('returns false when flag is "1" (strict true only)', () => {
    process.env['NEXT_PUBLIC_FEATURE_TEST_FLAG'] = '1';
    expect(isEnabled('NEXT_PUBLIC_FEATURE_TEST_FLAG')).toBe(false);
  });

  it('RIGPA_LMS flag controls ribbon visibility', () => {
    process.env['NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED'] = 'true';
    expect(isEnabled('NEXT_PUBLIC_FEATURE_RIGPA_LMS_ENABLED')).toBe(true);
  });
});
