/**
 * src/tests/unit/lib-utils-format.test.ts
 *
 * Coverage backfill for src/lib/utils/format.ts. Baseline was 70% lines,
 * uncovered range was formatRelativeTime (36-44). This spec covers all
 * five exports across their significant branches.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  formatDuration,
  formatCost,
  formatDate,
  formatStatus,
  formatRelativeTime,
} from '@/lib/utils/format';

describe('formatDuration', () => {
  it('returns em-dash when null', () => {
    expect(formatDuration(null)).toBe('—');
  });
  it('sub-minute in seconds', () => {
    expect(formatDuration(45_000)).toBe('45s');
    expect(formatDuration(0)).toBe('0s');
  });
  it('sub-hour in m + s', () => {
    expect(formatDuration(65_000)).toBe('1m 5s');
    expect(formatDuration(59 * 60_000 + 30_000)).toBe('59m 30s');
  });
  it('hour+ in h + m', () => {
    expect(formatDuration(60 * 60_000)).toBe('1h 0m');
    expect(formatDuration(2 * 60 * 60_000 + 15 * 60_000)).toBe('2h 15m');
  });
});

describe('formatCost', () => {
  it('em-dash when null', () => expect(formatCost(null)).toBe('—'));
  it('sub-cent shows <$0.01', () => {
    expect(formatCost(0.005)).toBe('<$0.01');
    expect(formatCost(0)).toBe('<$0.01');
  });
  it('formats with 3 decimals', () => {
    expect(formatCost(0.01)).toBe('$0.010');
    expect(formatCost(1.2345)).toBe('$1.235');
  });
});

describe('formatDate + formatRelativeTime', () => {
  const FIXED_NOW = new Date('2026-08-03T12:00:00Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_NOW);
  });
  afterEach(() => vi.useRealTimers());

  it('formatDate — just now (< 1 min)', () => {
    expect(formatDate(new Date(FIXED_NOW.getTime() - 30_000).toISOString())).toBe('just now');
  });
  it('formatDate — minutes ago', () => {
    expect(formatDate(new Date(FIXED_NOW.getTime() - 5 * 60_000).toISOString())).toBe('5m ago');
  });
  it('formatDate — hours ago', () => {
    expect(formatDate(new Date(FIXED_NOW.getTime() - 3 * 60 * 60_000).toISOString())).toBe('3h ago');
  });
  it('formatDate — locale date when > 24h', () => {
    const out = formatDate(new Date(FIXED_NOW.getTime() - 3 * 24 * 60 * 60_000).toISOString());
    // Format varies by locale, so just assert it's not one of the relative branches.
    expect(['just now'].includes(out)).toBe(false);
    expect(/ago$/.test(out)).toBe(false);
  });

  it('formatRelativeTime — accepts Date', () => {
    expect(formatRelativeTime(new Date(FIXED_NOW.getTime() - 30_000))).toBe('just now');
  });
  it('formatRelativeTime — accepts ISO string', () => {
    expect(formatRelativeTime(new Date(FIXED_NOW.getTime() - 10 * 60_000).toISOString())).toBe('10m ago');
  });
  it('formatRelativeTime — accepts epoch number', () => {
    expect(formatRelativeTime(FIXED_NOW.getTime() - 2 * 60 * 60_000)).toBe('2h ago');
  });
  it('formatRelativeTime — days ago (>24h)', () => {
    expect(formatRelativeTime(new Date(FIXED_NOW.getTime() - 5 * 24 * 60 * 60_000))).toBe('5d ago');
  });
});

describe('formatStatus', () => {
  it('replaces underscores with spaces', () => {
    expect(formatStatus('awaiting_approval')).toBe('awaiting approval');
    expect(formatStatus('idle')).toBe('idle');
    expect(formatStatus('multi_word_status')).toBe('multi word status');
  });
});
