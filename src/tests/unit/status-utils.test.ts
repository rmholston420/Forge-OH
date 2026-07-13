/**
 * Unit tests: run status color token and label mapping.
 * Ensures every valid RunStatus maps to a non-empty token and label.
 */
import { describe, it, expect } from 'vitest';

type RunStatus =
  | 'idle' | 'running' | 'streaming' | 'queued'
  | 'paused' | 'awaiting-approval' | 'succeeded'
  | 'failed' | 'blocked' | 'disconnected';

const STATUS_TOKEN: Record<RunStatus, string> = {
  idle: '--color-text-tertiary',
  running: '--color-state-running',
  streaming: '--color-accent-primary',
  queued: '--color-state-paused',
  paused: '--color-state-paused',
  'awaiting-approval': '--color-state-warning',
  succeeded: '--color-state-success',
  failed: '--color-state-error',
  blocked: '--color-state-error',
  disconnected: '--color-state-error',
};

const STATUS_LABEL: Record<RunStatus, string> = {
  idle: 'Idle',
  running: 'Running',
  streaming: 'Streaming',
  queued: 'Queued',
  paused: 'Paused',
  'awaiting-approval': 'Awaiting Approval',
  succeeded: 'Succeeded',
  failed: 'Failed',
  blocked: 'Blocked',
  disconnected: 'Disconnected',
};

const ALL_STATUSES: RunStatus[] = [
  'idle', 'running', 'streaming', 'queued', 'paused',
  'awaiting-approval', 'succeeded', 'failed', 'blocked', 'disconnected',
];

describe('status token mapping', () => {
  it('every status maps to a non-empty CSS token', () => {
    for (const s of ALL_STATUSES) {
      expect(STATUS_TOKEN[s]).toBeTruthy();
      expect(STATUS_TOKEN[s]).toMatch(/^--color-/);
    }
  });

  it('awaiting-approval maps to warning token', () => {
    expect(STATUS_TOKEN['awaiting-approval']).toBe('--color-state-warning');
  });

  it('succeeded maps to success token', () => {
    expect(STATUS_TOKEN['succeeded']).toBe('--color-state-success');
  });

  it('failed, blocked, disconnected all map to error token', () => {
    expect(STATUS_TOKEN['failed']).toBe('--color-state-error');
    expect(STATUS_TOKEN['blocked']).toBe('--color-state-error');
    expect(STATUS_TOKEN['disconnected']).toBe('--color-state-error');
  });
});

describe('status label mapping', () => {
  it('every status has a human-readable label', () => {
    for (const s of ALL_STATUSES) {
      expect(STATUS_LABEL[s]).toBeTruthy();
      expect(STATUS_LABEL[s].length).toBeGreaterThan(0);
    }
  });

  it('awaiting-approval label is "Awaiting Approval"', () => {
    expect(STATUS_LABEL['awaiting-approval']).toBe('Awaiting Approval');
  });
});
