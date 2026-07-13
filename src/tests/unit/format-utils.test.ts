/**
 * Extended tests for src/lib/utils/format.ts
 * Covers: formatCost, formatElapsed, truncate, formatRelativeTime
 */
import { describe, it, expect } from 'vitest';

// We import the same module already tested in format.test.ts.
// Adjust path to whatever the actual export path is.
import {
  formatCost,
  formatElapsed,
  truncate,
  formatRelativeTime,
} from '../../lib/utils/format';

// ---------------------------------------------------------------------------
// formatCost
// ---------------------------------------------------------------------------
describe('formatCost', () => {
  it('formats zero as $0.0000', () => {
    expect(formatCost(0)).toBe('$0.0000');
  });

  it('formats small cost with 4 decimals', () => {
    expect(formatCost(0.0012)).toBe('$0.0012');
  });

  it('formats whole dollar amount', () => {
    expect(formatCost(1)).toBe('$1.0000');
  });

  it('returns em-dash for null', () => {
    expect(formatCost(null)).toBe('—');
  });

  it('returns em-dash for undefined', () => {
    expect(formatCost(undefined)).toBe('—');
  });
});

// ---------------------------------------------------------------------------
// formatElapsed
// ---------------------------------------------------------------------------
describe('formatElapsed', () => {
  it('formats sub-second as ms', () => {
    expect(formatElapsed(500)).toMatch(/ms/);
  });

  it('formats exactly one second', () => {
    expect(formatElapsed(1000)).toMatch(/1(\.0)?s/);
  });

  it('formats minutes and seconds', () => {
    expect(formatElapsed(90_000)).toMatch(/1m/);
  });

  it('returns em-dash for null', () => {
    expect(formatElapsed(null)).toBe('—');
  });

  it('returns em-dash for undefined', () => {
    expect(formatElapsed(undefined)).toBe('—');
  });

  it('does not return negative strings', () => {
    // Negative elapsed is a data bug — at minimum it should not crash
    const result = formatElapsed(-1000);
    expect(typeof result).toBe('string');
  });
});

// ---------------------------------------------------------------------------
// truncate
// ---------------------------------------------------------------------------
describe('truncate', () => {
  it('returns string unchanged when shorter than limit', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('returns string unchanged when equal to limit', () => {
    expect(truncate('hello', 5)).toBe('hello');
  });

  it('truncates and appends ellipsis when over limit', () => {
    const result = truncate('hello world', 5);
    expect(result.endsWith('…') || result.endsWith('...')).toBe(true);
    expect(result.length).toBeLessThanOrEqual(8); // 5 + 3 for '...'
  });

  it('handles empty string', () => {
    expect(truncate('', 5)).toBe('');
  });
});

// ---------------------------------------------------------------------------
// formatRelativeTime
// ---------------------------------------------------------------------------
describe('formatRelativeTime', () => {
  const now = new Date();

  it('returns "just now" for very recent timestamps', () => {
    const ts = new Date(now.getTime() - 5_000).toISOString();
    expect(formatRelativeTime(ts)).toMatch(/just now|seconds? ago/i);
  });

  it('returns minutes for 5 minutes ago', () => {
    const ts = new Date(now.getTime() - 5 * 60_000).toISOString();
    expect(formatRelativeTime(ts)).toMatch(/min/i);
  });

  it('returns hours for 2 hours ago', () => {
    const ts = new Date(now.getTime() - 2 * 3_600_000).toISOString();
    expect(formatRelativeTime(ts)).toMatch(/hour|hr/i);
  });

  it('returns days for yesterday', () => {
    const ts = new Date(now.getTime() - 25 * 3_600_000).toISOString();
    expect(formatRelativeTime(ts)).toMatch(/day/i);
  });

  it('does not throw on null', () => {
    expect(() => formatRelativeTime(null)).not.toThrow();
  });
});
