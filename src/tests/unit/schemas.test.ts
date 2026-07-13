import { describe, it, expect } from 'vitest';
import { RunSummarySchema } from '@/lib/schemas/run';
import { mockRuns } from '../fixtures/runs.fixture';

describe('RunSummarySchema', () => {
  it('parses valid run fixture', () => {
    const result = RunSummarySchema.safeParse(mockRuns[0]);
    expect(result.success).toBe(true);
  });

  it('rejects missing required fields', () => {
    const result = RunSummarySchema.safeParse({ id: 'x' });
    expect(result.success).toBe(false);
  });
});
