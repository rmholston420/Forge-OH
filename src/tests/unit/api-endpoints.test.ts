/**
 * src/tests/unit/api-endpoints.test.ts
 *
 * Covers: src/lib/api/endpoints.ts
 * — Every ENDPOINTS namespace produces correct URL strings
 * — Parameter injection (no leaked placeholders)
 * — Special-char encoding on compare endpoint
 */
import { describe, it, expect } from 'vitest';
import { ENDPOINTS } from '@/lib/api/endpoints';

describe('ENDPOINTS.RUNS', () => {
  it('list returns /api/runs', () => {
    expect(ENDPOINTS.RUNS.list()).toBe('/api/runs');
  });
  it('create returns /api/runs', () => {
    expect(ENDPOINTS.RUNS.create()).toBe('/api/runs');
  });
  it('get injects runId', () => {
    expect(ENDPOINTS.RUNS.get('run-123')).toBe('/api/runs/run-123');
  });
  it('pause injects runId', () => {
    expect(ENDPOINTS.RUNS.pause('r1')).toBe('/api/runs/r1/pause');
  });
  it('resume injects runId', () => {
    expect(ENDPOINTS.RUNS.resume('r1')).toBe('/api/runs/r1/resume');
  });
  it('stop injects runId', () => {
    expect(ENDPOINTS.RUNS.stop('r1')).toBe('/api/runs/r1/stop');
  });
  it('fork injects runId', () => {
    expect(ENDPOINTS.RUNS.fork('r1')).toBe('/api/runs/r1/fork');
  });
  it('approve injects runId', () => {
    expect(ENDPOINTS.RUNS.approve('r1')).toBe('/api/runs/r1/approve');
  });
  it('reject injects runId', () => {
    expect(ENDPOINTS.RUNS.reject('r1')).toBe('/api/runs/r1/reject');
  });
  it('compare encodes both IDs as query params', () => {
    const url = ENDPOINTS.RUNS.compare('run-a', 'run-b');
    expect(url).toContain('left=run-a');
    expect(url).toContain('right=run-b');
    expect(url).toContain('/api/runs/compare');
  });
  it('compare URL-encodes special chars', () => {
    const url = ENDPOINTS.RUNS.compare('id with spaces', 'id/slash');
    expect(url).not.toContain(' ');
    expect(url).toContain(encodeURIComponent('id with spaces'));
  });
});

describe('ENDPOINTS.EVENTS', () => {
  it('list injects runId', () => {
    expect(ENDPOINTS.EVENTS.list('r42')).toBe('/api/runs/r42/events');
  });
});

describe('ENDPOINTS.ARTIFACTS', () => {
  it('list injects runId', () => {
    expect(ENDPOINTS.ARTIFACTS.list('r1')).toBe('/api/runs/r1/artifacts');
  });
  it('get injects runId and artifactId', () => {
    expect(ENDPOINTS.ARTIFACTS.get('r1', 'a1')).toBe('/api/runs/r1/artifacts/a1');
  });
  it('listFiles injects runId', () => {
    expect(ENDPOINTS.ARTIFACTS.listFiles('r1')).toBe('/api/runs/r1/artifacts/files');
  });
  it('diff encodes path param', () => {
    const url = ENDPOINTS.ARTIFACTS.diff('r1', 'src/main.py');
    expect(url).toContain('path=');
    expect(url).toContain(encodeURIComponent('src/main.py'));
  });
  it('exportPatch injects runId', () => {
    expect(ENDPOINTS.ARTIFACTS.exportPatch('r1')).toBe('/api/runs/r1/export/patch');
  });
});

describe('ENDPOINTS.WORKSPACES', () => {
  it('list returns /api/workspaces', () => {
    expect(ENDPOINTS.WORKSPACES.list()).toBe('/api/workspaces');
  });
  it('get injects id', () => {
    expect(ENDPOINTS.WORKSPACES.get('ws-1')).toBe('/api/workspaces/ws-1');
  });
  it('reset injects id', () => {
    expect(ENDPOINTS.WORKSPACES.reset('ws-1')).toBe('/api/workspaces/ws-1/reset');
  });
});

describe('ENDPOINTS.AGENTS', () => {
  it('listPresets returns /api/agents/presets', () => {
    expect(ENDPOINTS.AGENTS.listPresets()).toBe('/api/agents/presets');
  });
});

describe('ENDPOINTS.SECRETS', () => {
  it('list returns /api/secrets', () => {
    expect(ENDPOINTS.SECRETS.list()).toBe('/api/secrets');
  });
  it('create returns /api/secrets', () => {
    expect(ENDPOINTS.SECRETS.create()).toBe('/api/secrets');
  });
  it('update injects id', () => {
    expect(ENDPOINTS.SECRETS.update('s1')).toBe('/api/secrets/s1');
  });
  it('delete injects id', () => {
    expect(ENDPOINTS.SECRETS.delete('s1')).toBe('/api/secrets/s1');
  });
});

describe('ENDPOINTS.OBSERVABILITY', () => {
  it('summary returns /api/observability/summary', () => {
    expect(ENDPOINTS.OBSERVABILITY.summary()).toBe('/api/observability/summary');
  });
  it('runs returns /api/observability/runs', () => {
    expect(ENDPOINTS.OBSERVABILITY.runs()).toBe('/api/observability/runs');
  });
  it('errors returns /api/observability/errors', () => {
    expect(ENDPOINTS.OBSERVABILITY.errors()).toBe('/api/observability/errors');
  });
});

describe('ENDPOINTS.PLUGINS', () => {
  it('list returns /api/plugins', () => {
    expect(ENDPOINTS.PLUGINS.list()).toBe('/api/plugins');
  });
  it('enable injects id', () => {
    expect(ENDPOINTS.PLUGINS.enable('p1')).toBe('/api/plugins/p1/enable');
  });
  it('disable injects id', () => {
    expect(ENDPOINTS.PLUGINS.disable('p1')).toBe('/api/plugins/p1/disable');
  });
});

describe('ENDPOINTS.BROWSER', () => {
  it('listSessions injects runId', () => {
    expect(ENDPOINTS.BROWSER.listSessions('r1')).toBe('/api/runs/r1/browser/sessions');
  });
  it('getSession injects runId and sessionId', () => {
    expect(ENDPOINTS.BROWSER.getSession('r1', 's1')).toBe('/api/runs/r1/browser/sessions/s1');
  });
});

describe('ENDPOINTS — no raw placeholders leak', () => {
  it('no endpoint contains undefined or :param after substitution', () => {
    const urls = [
      ENDPOINTS.RUNS.get('x'), ENDPOINTS.ARTIFACTS.get('r', 'a'),
      ENDPOINTS.WORKSPACES.get('w'), ENDPOINTS.SECRETS.update('s'),
      ENDPOINTS.PLUGINS.enable('p'), ENDPOINTS.BROWSER.getSession('r', 's'),
    ];
    for (const url of urls) {
      expect(url).not.toContain(':');
      expect(url).not.toContain('undefined');
    }
  });
});
