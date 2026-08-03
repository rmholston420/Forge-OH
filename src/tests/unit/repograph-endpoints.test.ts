/**
 * src/tests/unit/repograph-endpoints.test.ts
 *
 * Covers: src/lib/api/endpoints.ts \u2014 REPOGRAPH namespace.
 * Every route mirrors one in bff/routers/repograph.py (Slice D.4).
 */
import { describe, it, expect } from 'vitest';
import { ENDPOINTS } from '@/lib/api/endpoints';

describe('ENDPOINTS.REPOGRAPH', () => {
  it('health', () =>
    expect(ENDPOINTS.REPOGRAPH.health()).toBe('/api/repograph/health'));

  it('index', () =>
    expect(ENDPOINTS.REPOGRAPH.index()).toBe('/api/repograph/index'));

  it('search encodes repo_key, q, limit', () => {
    const url = ENDPOINTS.REPOGRAPH.search('rk 1', 'foo bar', 25);
    expect(url).toBe(
      '/api/repograph/search?repo_key=rk%201&q=foo%20bar&limit=25',
    );
  });

  it('search uses default limit 20', () => {
    const url = ENDPOINTS.REPOGRAPH.search('rk1', 'foo');
    expect(url).toContain('limit=20');
  });

  it('callers with rel_path', () => {
    const url = ENDPOINTS.REPOGRAPH.callers('rk1', 'hello', 'lib/thing.py', 5);
    expect(url).toBe(
      '/api/repograph/callers?repo_key=rk1&name=hello' +
        '&rel_path=lib%2Fthing.py&limit=5',
    );
  });

  it('callers without rel_path omits param', () => {
    const url = ENDPOINTS.REPOGRAPH.callers('rk1', 'hello');
    expect(url).not.toContain('rel_path=');
  });

  it('callees', () => {
    const url = ENDPOINTS.REPOGRAPH.callees('rk1', 'bff/main.py', 5);
    expect(url).toBe(
      '/api/repograph/callees?repo_key=rk1&rel_path=bff%2Fmain.py&limit=5',
    );
  });

  it('coChanged with defaults', () => {
    const url = ENDPOINTS.REPOGRAPH.coChanged('rk1', 'bff/main.py');
    expect(url).toContain('window=50');
    expect(url).toContain('limit=10');
  });

  it('coChanged with custom window and limit', () => {
    const url = ENDPOINTS.REPOGRAPH.coChanged('rk1', 'x.py', 30, 5);
    expect(url).toContain('window=30');
    expect(url).toContain('limit=5');
  });

  it('contextBundle', () =>
    expect(ENDPOINTS.REPOGRAPH.contextBundle()).toBe(
      '/api/repograph/context_bundle',
    ));
});
