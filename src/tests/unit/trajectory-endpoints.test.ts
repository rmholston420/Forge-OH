/**
 * src/tests/unit/trajectory-endpoints.test.ts
 *
 * Covers: src/lib/api/endpoints.ts — TRAJECTORIES namespace.
 * Every route mirrors one in bff/routers/trajectories.py (Slice F.6).
 */
import { describe, it, expect } from 'vitest';
import { ENDPOINTS } from '@/lib/api/endpoints';

describe('ENDPOINTS.TRAJECTORIES', () => {
  it('list without params', () =>
    expect(ENDPOINTS.TRAJECTORIES.list()).toBe('/api/trajectories'));

  it('list with limit only', () =>
    expect(ENDPOINTS.TRAJECTORIES.list({ limit: 10 })).toBe(
      '/api/trajectories?limit=10',
    ));

  it('list with status encoded', () =>
    expect(ENDPOINTS.TRAJECTORIES.list({ status: 'succ ess' })).toBe(
      '/api/trajectories?status=succ%20ess',
    ));

  it('list with repoKey encoded', () =>
    expect(ENDPOINTS.TRAJECTORIES.list({ repoKey: 'r/k 1' })).toBe(
      '/api/trajectories?repo_key=r%2Fk%201',
    ));

  it('list combines all params in order limit,status,repoKey', () =>
    expect(
      ENDPOINTS.TRAJECTORIES.list({
        limit: 5,
        status: 'success',
        repoKey: 'rk1',
      }),
    ).toBe('/api/trajectories?limit=5&status=success&repo_key=rk1'));

  it('get encodes trajectory id', () =>
    expect(ENDPOINTS.TRAJECTORIES.get('traj/abc def')).toBe(
      '/api/trajectories/traj%2Fabc%20def',
    ));

  it('search is a plain POST endpoint', () =>
    expect(ENDPOINTS.TRAJECTORIES.search()).toBe('/api/trajectories/search'));
});
