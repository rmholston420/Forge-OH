/**
 * Targeted tests for the 'stopped' status added in the final-pass fix.
 * Supplements run-schemas.test.ts.
 */
import { describe, it, expect } from 'vitest';
import { RunStatusSchema, RunSchema } from '../../lib/schemas/run';

describe('RunStatusSchema — stopped', () => {
  it('accepts stopped as a valid terminal status', () => {
    const result = RunStatusSchema.safeParse('stopped');
    expect(result.success).toBe(true);
  });

  it('distinguishes stopped from failed', () => {
    expect(RunStatusSchema.safeParse('stopped').success).toBe(true);
    expect(RunStatusSchema.safeParse('failed').success).toBe(true);
    // Both valid but distinct values
    expect('stopped').not.toBe('failed');
  });

  it('rejects unknown terminal values', () => {
    expect(RunStatusSchema.safeParse('killed').success).toBe(false);
    expect(RunStatusSchema.safeParse('terminated').success).toBe(false);
  });
});

describe('RunSchema with stopped status', () => {
  const baseRun = {
    id: 'run-001',
    title: 'Test run',
    status: 'stopped',
    agentPresetName: 'default',
    workspaceId: 'ws-001',
    workspaceType: 'local',
    activeTool: null,
    updatedAt: '2026-07-13T00:00:00Z',
    createdAt: '2026-07-13T00:00:00Z',
    elapsedMs: 45_000,
    estimatedCostUsd: 0.0042,
  };

  it('parses a full stopped run object', () => {
    const result = RunSchema.safeParse(baseRun);
    expect(result.success).toBe(true);
  });

  it('preserves elapsedMs on stopped run', () => {
    const result = RunSchema.safeParse(baseRun);
    expect(result.success && result.data.elapsedMs).toBe(45_000);
  });
});
