/**
 * src/tests/unit/replay-schemas.test.ts
 */
import { describe, it, expect } from 'vitest';
import { PlaybackSpeedSchema, RunReplayStateSchema } from '@/features/run-replay/schemas';

describe('PlaybackSpeedSchema', () => {
  it.each([0.25, 0.5, 1, 2, 4])('accepts speed=%s', (speed) => {
    expect(PlaybackSpeedSchema.safeParse(speed).success).toBe(true);
  });

  it.each([0, 0.1, 3, 8, '1', null])('rejects invalid=%s', (v) => {
    expect(PlaybackSpeedSchema.safeParse(v).success).toBe(false);
  });
});

describe('RunReplayStateSchema', () => {
  const valid = {
    runId: 'run-abc',
    totalEvents: 100,
    currentIndex: 10,
    isPlaying: false,
    playbackSpeed: 1,
    isLooping: false,
  };

  it('accepts a valid replay state', () => {
    expect(RunReplayStateSchema.safeParse(valid).success).toBe(true);
  });

  it('accepts with optional currentTimestamp', () => {
    expect(RunReplayStateSchema.safeParse({ ...valid, currentTimestamp: '2026-01-01T00:00:00Z' }).success).toBe(true);
  });

  it('rejects when totalEvents is negative', () => {
    expect(RunReplayStateSchema.safeParse({ ...valid, totalEvents: -1 }).success).toBe(false);
  });

  it('rejects invalid playbackSpeed', () => {
    expect(RunReplayStateSchema.safeParse({ ...valid, playbackSpeed: 3 }).success).toBe(false);
  });

  it('rejects missing required fields', () => {
    const { runId: _, ...rest } = valid;
    expect(RunReplayStateSchema.safeParse(rest).success).toBe(false);
  });
});
