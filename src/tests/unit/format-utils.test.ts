/**
 * format-utils.test.ts
 *
 * Full branch coverage for every function in src/lib/utils/format.ts.
 * These are pure functions so no mocks are needed. Every branch in every
 * conditional must be exercised; untested branches mean silent regressions
 * whenever display strings are refactored.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { formatDuration, formatCost, formatDate, formatStatus } from '@/lib/utils/format';

// ---------------------------------------------------------------------------
// formatDuration
// ---------------------------------------------------------------------------
describe('formatDuration', () => {
  it('returns em-dash for null', () => {
    expect(formatDuration(null)).toBe('\u2014');
  });

  it('formats 0ms as 0s', () => {
    expect(formatDuration(0)).toBe('0s');
  });

  it('formats sub-minute durations in seconds', () => {
    expect(formatDuration(1000)).toBe('1s');
    expect(formatDuration(59_000)).toBe('59s');
    expect(formatDuration(59_999)).toBe('59s'); // floor
  });

  it('formats exactly 60 s as 1m 0s', () => {
    expect(formatDuration(60_000)).toBe('1m 0s');
  });

  it('formats minutes with remainder seconds', () => {
    expect(formatDuration(90_000)).toBe('1m 30s');
    expect(formatDuration(3599_000)).toBe('59m 59s');
  });

  it('formats exactly 1 hour', () => {
    expect(formatDuration(3_600_000)).toBe('1h 0m');
  });

  it('formats multi-hour durations', () => {
    expect(formatDuration(3_661_000)).toBe('1h 1m');
    expect(formatDuration(7_322_000)).toBe('2h 2m');
  });

  it('floors milliseconds — does not round up', () => {
    // 1999 ms = 1s, not 2s
    expect(formatDuration(1_999)).toBe('1s');
  });
});

// ---------------------------------------------------------------------------
// formatCost
// ---------------------------------------------------------------------------
describe('formatCost', () => {
  it('returns em-dash for null', () => {
    expect(formatCost(null)).toBe('\u2014');
  });

  it('returns "<$0.01" for values below the cent threshold', () => {
    expect(formatCost(0)).toBe('<$0.01');
    expect(formatCost(0.0001)).toBe('<$0.01');
    expect(formatCost(0.0099)).toBe('<$0.01');
  });

  it('returns exactly "<$0.01" at the boundary exclusive', () => {
    // 0.01 itself is NOT below threshold
    expect(formatCost(0.01)).toBe('$0.010');
  });

  it('formats values with 3 decimal places', () => {
    expect(formatCost(0.123)).toBe('$0.123');
    expect(formatCost(1)).toBe('$1.000');
    expect(formatCost(12.5)).toBe('$12.500');
  });

  it('formats large cost correctly', () => {
    expect(formatCost(100)).toBe('$100.000');
  });
});

// ---------------------------------------------------------------------------
// formatDate
// ---------------------------------------------------------------------------
describe('formatDate', () => {
  beforeEach(() => {
    // Pin "now" to a fixed timestamp so relative formatting is deterministic.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-13T12:00:00.000Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "just now" for timestamps less than 1 minute ago', () => {
    expect(formatDate('2026-07-13T11:59:30.000Z')).toBe('just now');
    expect(formatDate('2026-07-13T12:00:00.000Z')).toBe('just now');
  });

  it('returns "Xm ago" for timestamps 1–59 minutes ago', () => {
    expect(formatDate('2026-07-13T11:59:00.000Z')).toBe('1m ago');
    expect(formatDate('2026-07-13T11:30:00.000Z')).toBe('30m ago');
    expect(formatDate('2026-07-13T11:01:00.000Z')).toBe('59m ago');
  });

  it('returns "Xh ago" for timestamps 1–23 hours ago', () => {
    expect(formatDate('2026-07-13T11:00:00.000Z')).toBe('1h ago');
    expect(formatDate('2026-07-13T00:00:00.000Z')).toBe('12h ago');
    expect(formatDate('2026-07-12T13:00:00.000Z')).toBe('23h ago');
  });

  it('returns a locale date string for timestamps ≥24 hours ago', () => {
    const iso = '2026-07-12T11:59:00.000Z'; // >24h ago
    const result = formatDate(iso);
    // Must be a non-empty string (locale-specific, so we only assert shape)
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
    // Must NOT be a relative string
    expect(result).not.toMatch(/ago$/);
    expect(result).not.toBe('just now');
  });
});

// ---------------------------------------------------------------------------
// formatStatus
// ---------------------------------------------------------------------------
describe('formatStatus', () => {
  it('replaces underscores with spaces', () => {
    expect(formatStatus('pending_approval')).toBe('pending approval');
    expect(formatStatus('running_with_errors')).toBe('running with errors');
  });

  it('leaves strings without underscores unchanged', () => {
    expect(formatStatus('running')).toBe('running');
    expect(formatStatus('failed')).toBe('failed');
  });

  it('handles multiple consecutive underscores', () => {
    expect(formatStatus('a__b')).toBe('a  b');
  });

  it('handles leading and trailing underscores', () => {
    expect(formatStatus('_status_')).toBe(' status ');
  });

  it('handles empty string', () => {
    expect(formatStatus('')).toBe('');
  });
});
