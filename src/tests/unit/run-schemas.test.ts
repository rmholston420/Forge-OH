/**
 * Unit tests: src/lib/schemas/run.ts
 *
 * Verifies all RunStatus enum values including the 'stopped' terminal state
 * added in the last fix pass. Also covers RunSummarySchema and
 * RunDetailUIStateSchema structural validation.
 */
import { describe, it, expect } from 'vitest';
import { RunStatusSchema, RunSummarySchema, RunDetailUIStateSchema } from '@/lib/schemas/run';

const ALL_STATUSES = [
  'idle', 'running', 'streaming', 'queued', 'paused',
  'awaiting_approval', 'succeeded', 'failed', 'blocked', 'stopped',
] as const;

describe('RunStatusSchema', () => {
  it.each(ALL_STATUSES)('accepts status: %s', (status) => {
    expect(RunStatusSchema.safeParse(status).success).toBe(true);
  });

  it("accepts 'stopped' — the terminal state added in fix pass", () => {
    expect(RunStatusSchema.safeParse('stopped').success).toBe(true);
  });

  it('rejects unknown status', () => {
    expect(RunStatusSchema.safeParse('cancelled').success).toBe(false);
  });

  it('rejects empty string', () => {
    expect(RunStatusSchema.safeParse('').success).toBe(false);
  });
});

describe('RunSummarySchema', () => {
  const validRun = {
    id: 'run-001', title: 'Test run', status: 'running',
    agentPresetName: 'default', workspaceId: 'ws-1',
    workspaceType: 'docker', activeTool: null,
    updatedAt: new Date().toISOString(), createdAt: new Date().toISOString(),
    elapsedMs: null, estimatedCostUsd: null,
  };

  it('parses a valid run summary', () => {
    expect(RunSummarySchema.safeParse(validRun).success).toBe(true);
  });

  it('accepts stopped status in a run summary', () => {
    expect(RunSummarySchema.safeParse({ ...validRun, status: 'stopped' }).success).toBe(true);
  });

  it('rejects missing id', () => {
    const { id: _, ...noId } = validRun;
    expect(RunSummarySchema.safeParse(noId).success).toBe(false);
  });

  it('rejects invalid workspaceType', () => {
    expect(RunSummarySchema.safeParse({ ...validRun, workspaceType: 'k8s' }).success).toBe(false);
  });
});

describe('RunDetailUIStateSchema', () => {
  it('parses valid UI state', () => {
    expect(RunDetailUIStateSchema.safeParse({
      selectedTab: 'overview', selectedEventId: null,
      diffMode: 'split', inspectorOpen: false, latestStreamEventId: 0,
    }).success).toBe(true);
  });

  it('rejects unknown tab', () => {
    expect(RunDetailUIStateSchema.safeParse({
      selectedTab: 'debug', selectedEventId: null,
      diffMode: 'split', inspectorOpen: false, latestStreamEventId: 0,
    }).success).toBe(false);
  });
});
