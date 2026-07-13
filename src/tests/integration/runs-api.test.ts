import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '../mocks/server';
import { fetchRuns } from '@/features/runs/api';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('fetchRuns', () => {
  it('returns an array', async () => {
    const runs = await fetchRuns();
    expect(Array.isArray(runs)).toBe(true);
  });
});
