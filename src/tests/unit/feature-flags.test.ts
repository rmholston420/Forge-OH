/**
 * feature-flags.test.ts
 *
 * Tests for src/lib/feature-flags/index.ts.
 *
 * Covers:
 *   - isFeatureEnabled: true only for "true" (case-insensitive)
 *   - isFeatureEnabled: absent/undefined/empty/"false"/"1" all return false
 *   - requireFeatureFlag: throws when disabled, no-ops when enabled
 *   - getAllFlags: returns an entry for every registered flag
 *   - getAllFlags: returns false for all flags when no env vars are set
 *   - FEATURE_FLAGS registry: no duplicate values, all values are strings
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  isFeatureEnabled,
  requireFeatureFlag,
  getAllFlags,
  FEATURE_FLAGS,
} from '@/lib/feature-flags';
import type { FeatureFlag } from '@/lib/feature-flags';

// Store the original process.env so we can restore it after each test.
const originalEnv = process.env;

beforeEach(() => {
  // Give each test a clean, isolated env object.
  process.env = { ...originalEnv };
  // Ensure all feature flags are unset by default.
  for (const flag of Object.values(FEATURE_FLAGS)) {
    delete process.env[`NEXT_PUBLIC_FEATURE_${flag}`];
  }
});

afterEach(() => {
  process.env = originalEnv;
});

// ---------------------------------------------------------------------------
// isFeatureEnabled
// ---------------------------------------------------------------------------
describe('isFeatureEnabled', () => {
  it('returns true when env var is "true"', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'true';
    expect(isFeatureEnabled('RUN_LIST')).toBe(true);
  });

  it('returns true for uppercase "TRUE" (case-insensitive)', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'TRUE';
    expect(isFeatureEnabled('RUN_LIST')).toBe(true);
  });

  it('returns true for mixed-case "True"', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'True';
    expect(isFeatureEnabled('RUN_LIST')).toBe(true);
  });

  it('returns false when env var is absent', () => {
    expect(isFeatureEnabled('RUN_LIST')).toBe(false);
  });

  it('returns false for "false"', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'false';
    expect(isFeatureEnabled('RUN_LIST')).toBe(false);
  });

  it('returns false for "1" (not accepted as truthy)', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = '1';
    expect(isFeatureEnabled('RUN_LIST')).toBe(false);
  });

  it('returns false for empty string', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = '';
    expect(isFeatureEnabled('RUN_LIST')).toBe(false);
  });

  it('returns false for "yes"', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'yes';
    expect(isFeatureEnabled('RUN_LIST')).toBe(false);
  });

  it('is independent per flag — enabling one does not enable another', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_LIST'] = 'true';
    expect(isFeatureEnabled('LIVE_STREAM')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// requireFeatureFlag
// ---------------------------------------------------------------------------
describe('requireFeatureFlag', () => {
  it('throws when flag is disabled', () => {
    expect(() => requireFeatureFlag('PLUGIN_MARKETPLACE')).toThrow(
      'Feature "PLUGIN_MARKETPLACE" is disabled',
    );
  });

  it('throws with a message including the env var name', () => {
    expect(() => requireFeatureFlag('RIGPA_LMS')).toThrow(
      'NEXT_PUBLIC_FEATURE_RIGPA_LMS',
    );
  });

  it('does not throw when flag is enabled', () => {
    process.env['NEXT_PUBLIC_FEATURE_RUN_REPLAY'] = 'true';
    expect(() => requireFeatureFlag('RUN_REPLAY')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// getAllFlags
// ---------------------------------------------------------------------------
describe('getAllFlags', () => {
  it('returns an entry for every registered flag', () => {
    const flags = getAllFlags();
    for (const flag of Object.values(FEATURE_FLAGS)) {
      expect(flags).toHaveProperty(flag as FeatureFlag);
    }
  });

  it('all flags are false when no env vars are set', () => {
    const flags = getAllFlags();
    expect(Object.values(flags).every((v) => v === false)).toBe(true);
  });

  it('reflects individual flag when set to true', () => {
    process.env['NEXT_PUBLIC_FEATURE_TRACE_VIEWER'] = 'true';
    const flags = getAllFlags();
    expect(flags['TRACE_VIEWER']).toBe(true);
    // All others must remain false
    const others = Object.entries(flags).filter(([k]) => k !== 'TRACE_VIEWER');
    expect(others.every(([, v]) => v === false)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// FEATURE_FLAGS registry invariants
// ---------------------------------------------------------------------------
describe('FEATURE_FLAGS registry', () => {
  it('has no duplicate values', () => {
    const values = Object.values(FEATURE_FLAGS);
    expect(values.length).toBe(new Set(values).size);
  });

  it('all keys and values are non-empty strings', () => {
    for (const [key, value] of Object.entries(FEATURE_FLAGS)) {
      expect(typeof key).toBe('string');
      expect(key.length).toBeGreaterThan(0);
      expect(typeof value).toBe('string');
      expect((value as string).length).toBeGreaterThan(0);
    }
  });

  it('contains exactly 20 flags (full phase 0-5 registry)', () => {
    expect(Object.keys(FEATURE_FLAGS).length).toBe(20);
  });
});
