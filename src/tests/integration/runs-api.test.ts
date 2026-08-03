import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '../mocks/server';
import { fetchRuns } from '@/features/runs/api';

// MSW server lifecycle handled globally in src/tests/setup.ts
// (afterEach reset handled globally)
// (afterAll close handled globally)

describe('fetchRuns', () => {
  it('returns an array', async () => {
    const runs = await fetchRuns();
    expect(Array.isArray(runs)).toBe(true);
  });
});
