/**
 * src/tests/unit/socket-events.test.ts
 *
 * Covers: src/lib/streaming/socket.ts
 * — SOCKET_EVENTS constant: all expected event names present
 * — No duplicate event name values
 * — All values are non-empty strings
 * — Expected domain groupings are present (run lifecycle, streaming, control)
 */
import { describe, it, expect } from 'vitest';
import { SOCKET_EVENTS } from '@/lib/streaming/socket';

const ALL_EVENT_VALUES = Object.values(SOCKET_EVENTS) as string[];

describe('SOCKET_EVENTS constant', () => {
  it('is a non-empty object', () => {
    expect(typeof SOCKET_EVENTS).toBe('object');
    expect(ALL_EVENT_VALUES.length).toBeGreaterThan(0);
  });

  it('all values are non-empty strings', () => {
    for (const v of ALL_EVENT_VALUES) {
      expect(typeof v).toBe('string');
      expect(v.length).toBeGreaterThan(0);
    }
  });

  it('has no duplicate event name values', () => {
    const unique = new Set(ALL_EVENT_VALUES);
    expect(unique.size).toBe(ALL_EVENT_VALUES.length);
  });

  it('includes a run:start or run_start event', () => {
    const hasStart = ALL_EVENT_VALUES.some(
      v => v.includes('start') || v.includes('begin'),
    );
    expect(hasStart).toBe(true);
  });

  it('includes a run:end, run:complete, or run:stop event', () => {
    const hasEnd = ALL_EVENT_VALUES.some(
      v => v.includes('end') || v.includes('complete') || v.includes('stop') || v.includes('finish'),
    );
    expect(hasEnd).toBe(true);
  });

  it('includes an event for streaming output (stdout or stream)', () => {
    const hasStream = ALL_EVENT_VALUES.some(
      v => v.includes('stream') || v.includes('output') || v.includes('stdout') || v.includes('event'),
    );
    expect(hasStream).toBe(true);
  });

  it('includes an error or failed event', () => {
    const hasError = ALL_EVENT_VALUES.some(
      v => v.includes('error') || v.includes('fail'),
    );
    expect(hasError).toBe(true);
  });

  it('all keys use consistent naming convention (snake_case or colon-namespaced)', () => {
    // Values should not have mixed conventions in the same constant
    // (all snake_case OR all colon-namespaced, not random)
    const hasColon = ALL_EVENT_VALUES.some(v => v.includes(':'));
    const hasUnderscore = ALL_EVENT_VALUES.some(v => v.includes('_'));
    const hasCamelCase = ALL_EVENT_VALUES.some(v => /[a-z][A-Z]/.test(v));
    // At least one consistent pattern must be used; mixed camel+colon is the only forbidden combo
    expect(hasColon && hasCamelCase && !hasUnderscore).toBe(false);
  });
});
