/**
 * src/tests/unit/api-endpoints.test.ts
 *
 * Covers: src/lib/api/endpoints.ts
 * — Every ENDPOINTS namespace produces correct URL strings
 * — Parameter injection (no leaked placeholders)
 * — Special-char encoding on compare + file paths
 *
 * The registry is the source of truth for BFF URLs; each assertion is
 * mirrored by an actual BFF route in bff/routers/*.py.
 */
import { describe, it, expect } from 'vitest';
import { ENDPOINTS } from '@/lib/api/endpoints';

describe('ENDPOINTS.RUNS', () => {
  it('list', () => expect(ENDPOINTS.RUNS.list()).toBe('/api/runs'));
  it('create', () => expect(ENDPOINTS.RUNS.create()).toBe('/api/runs'));
  it('get', () => expect(ENDPOINTS.RUNS.get('r1')).toBe('/api/runs/r1'));
  it('plan', () => expect(ENDPOINTS.RUNS.plan('r1')).toBe('/api/runs/r1/plan'));
  it('pause', () => expect(ENDPOINTS.RUNS.pause('r1')).toBe('/api/runs/r1/pause'));
  it('resume', () => expect(ENDPOINTS.RUNS.resume('r1')).toBe('/api/runs/r1/resume'));
  it('stop', () => expect(ENDPOINTS.RUNS.stop('r1')).toBe('/api/runs/r1/stop'));
  it('fork', () => expect(ENDPOINTS.RUNS.fork('r1')).toBe('/api/runs/r1/fork'));
  it('approve', () => expect(ENDPOINTS.RUNS.approve('r1')).toBe('/api/runs/r1/approve'));
  it('reject', () => expect(ENDPOINTS.RUNS.reject('r1')).toBe('/api/runs/r1/reject'));
  it('secrets', () => expect(ENDPOINTS.RUNS.secrets('r1')).toBe('/api/runs/r1/secrets'));
  it('compare encodes IDs as query params', () => {
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
  it('list', () => expect(ENDPOINTS.EVENTS.list('r42')).toBe('/api/runs/r42/events'));
});

describe('ENDPOINTS.ARTIFACTS', () => {
  it('list', () => expect(ENDPOINTS.ARTIFACTS.list('r1')).toBe('/api/runs/r1/artifacts'));
});

describe('ENDPOINTS.COMMANDS', () => {
  it('list', () => expect(ENDPOINTS.COMMANDS.list('r1')).toBe('/api/runs/r1/commands'));
});

describe('ENDPOINTS.TRACES', () => {
  it('list', () => expect(ENDPOINTS.TRACES.list('r1')).toBe('/api/runs/r1/traces'));
});

describe('ENDPOINTS.BROWSER', () => {
  it('frames', () => expect(ENDPOINTS.BROWSER.frames('r1')).toBe('/api/runs/r1/browser'));
});

describe('ENDPOINTS.FILES', () => {
  it('list', () => expect(ENDPOINTS.FILES.list('r1')).toBe('/api/runs/r1/files'));
  it('get encodes path', () => {
    const url = ENDPOINTS.FILES.get('r1', 'src/main.py');
    expect(url).toContain(encodeURIComponent('src/main.py'));
  });
});

describe('ENDPOINTS.WORKSPACES', () => {
  it('list', () => expect(ENDPOINTS.WORKSPACES.list()).toBe('/api/workspaces'));
  it('get', () => expect(ENDPOINTS.WORKSPACES.get('w1')).toBe('/api/workspaces/w1'));
  it('create', () => expect(ENDPOINTS.WORKSPACES.create()).toBe('/api/workspaces'));
  it('update', () => expect(ENDPOINTS.WORKSPACES.update('w1')).toBe('/api/workspaces/w1'));
  it('delete', () => expect(ENDPOINTS.WORKSPACES.delete('w1')).toBe('/api/workspaces/w1'));
  it('test', () => expect(ENDPOINTS.WORKSPACES.test('w1')).toBe('/api/workspaces/w1/test'));
});

describe('ENDPOINTS.AGENTS', () => {
  it('listPresets', () => expect(ENDPOINTS.AGENTS.listPresets()).toBe('/api/agent-presets'));
  it('getPreset', () => expect(ENDPOINTS.AGENTS.getPreset('p1')).toBe('/api/agent-presets/p1'));
  it('createPreset', () => expect(ENDPOINTS.AGENTS.createPreset()).toBe('/api/agent-presets'));
  it('updatePreset', () => expect(ENDPOINTS.AGENTS.updatePreset('p1')).toBe('/api/agent-presets/p1'));
  it('deletePreset', () => expect(ENDPOINTS.AGENTS.deletePreset('p1')).toBe('/api/agent-presets/p1'));
  it('duplicatePreset', () => expect(ENDPOINTS.AGENTS.duplicatePreset('p1')).toBe('/api/agent-presets/p1/duplicate'));
  it('setDefaultPreset', () => expect(ENDPOINTS.AGENTS.setDefaultPreset('p1')).toBe('/api/agent-presets/p1/set-default'));
});

describe('ENDPOINTS.MCP', () => {
  it('list', () => expect(ENDPOINTS.MCP.list()).toBe('/api/mcp'));
  it('create', () => expect(ENDPOINTS.MCP.create()).toBe('/api/mcp'));
  it('delete', () => expect(ENDPOINTS.MCP.delete('m1')).toBe('/api/mcp/m1'));
  it('ping', () => expect(ENDPOINTS.MCP.ping('m1')).toBe('/api/mcp/m1/ping'));
  it('toggle', () => expect(ENDPOINTS.MCP.toggle('m1')).toBe('/api/mcp/m1/toggle'));
});

describe('ENDPOINTS.PLUGINS', () => {
  it('list', () => expect(ENDPOINTS.PLUGINS.list()).toBe('/api/plugins'));
  it('marketplace', () => expect(ENDPOINTS.PLUGINS.marketplace()).toBe('/api/plugins/marketplace'));
  it('create', () => expect(ENDPOINTS.PLUGINS.create()).toBe('/api/plugins'));
  it('install', () => expect(ENDPOINTS.PLUGINS.install()).toBe('/api/plugins/install'));
  it('enable', () => expect(ENDPOINTS.PLUGINS.enable('p1')).toBe('/api/plugins/p1/enable'));
  it('disable', () => expect(ENDPOINTS.PLUGINS.disable('p1')).toBe('/api/plugins/p1/disable'));
  it('uninstall', () => expect(ENDPOINTS.PLUGINS.uninstall('p1')).toBe('/api/plugins/p1'));
  it('ping', () => expect(ENDPOINTS.PLUGINS.ping('p1')).toBe('/api/plugins/p1/ping'));
});

describe('ENDPOINTS.SECRETS', () => {
  it('list', () => expect(ENDPOINTS.SECRETS.list()).toBe('/api/secrets'));
  it('create', () => expect(ENDPOINTS.SECRETS.create()).toBe('/api/secrets'));
  it('rotate', () => expect(ENDPOINTS.SECRETS.rotate('s1')).toBe('/api/secrets/s1/rotate'));
  it('delete', () => expect(ENDPOINTS.SECRETS.delete('s1')).toBe('/api/secrets/s1'));
});

describe('ENDPOINTS.NOTIFICATIONS', () => {
  it('list', () => expect(ENDPOINTS.NOTIFICATIONS.list()).toBe('/api/notifications'));
  it('markRead', () => expect(ENDPOINTS.NOTIFICATIONS.markRead('n1')).toBe('/api/notifications/n1/read'));
  it('markAllRead', () => expect(ENDPOINTS.NOTIFICATIONS.markAllRead()).toBe('/api/notifications/read-all'));
  it('delete', () => expect(ENDPOINTS.NOTIFICATIONS.delete('n1')).toBe('/api/notifications/n1'));
});

describe('ENDPOINTS.METRICS', () => {
  it('summary encodes period', () => expect(ENDPOINTS.METRICS.summary('7d')).toBe('/api/metrics/summary?period=7d'));
  it('daily', () => expect(ENDPOINTS.METRICS.daily('30d')).toBe('/api/metrics/daily?period=30d'));
  it('models', () => expect(ENDPOINTS.METRICS.models('90d')).toBe('/api/metrics/models?period=90d'));
  it('workspaces', () => expect(ENDPOINTS.METRICS.workspaces('all')).toBe('/api/metrics/workspaces?period=all'));
  it('global', () => expect(ENDPOINTS.METRICS.global()).toBe('/api/metrics'));
  it('forRun', () => expect(ENDPOINTS.METRICS.forRun('r1')).toBe('/api/metrics/runs/r1'));
  it('forWorkspace', () => expect(ENDPOINTS.METRICS.forWorkspace('w1')).toBe('/api/metrics/workspaces/w1'));
  it('cost', () => expect(ENDPOINTS.METRICS.cost()).toBe('/api/metrics/cost'));
});

describe('ENDPOINTS.SETTINGS', () => {
  it('get', () => expect(ENDPOINTS.SETTINGS.get()).toBe('/api/settings'));
  it('patch', () => expect(ENDPOINTS.SETTINGS.patch()).toBe('/api/settings'));
  it('reset', () => expect(ENDPOINTS.SETTINGS.reset()).toBe('/api/settings/reset'));
  it('modelRouting', () => expect(ENDPOINTS.SETTINGS.modelRouting()).toBe('/api/settings/model-routing'));
});

describe('ENDPOINTS.OBSERVABILITY', () => {
  it('traces', () => expect(ENDPOINTS.OBSERVABILITY.traces()).toBe('/api/observability/traces'));
  it('tracesForRun', () => expect(ENDPOINTS.OBSERVABILITY.tracesForRun('r1')).toBe('/api/observability/runs/r1/traces'));
  it('trace', () => expect(ENDPOINTS.OBSERVABILITY.trace('t1')).toBe('/api/observability/traces/t1'));
  it('spans', () => expect(ENDPOINTS.OBSERVABILITY.spans('t1')).toBe('/api/observability/traces/t1/spans'));
});

describe('ENDPOINTS — no raw placeholders leak', () => {
  it('no endpoint contains undefined or :param after substitution', () => {
    const urls = [
      ENDPOINTS.RUNS.get('x'),
      ENDPOINTS.ARTIFACTS.list('r'),
      ENDPOINTS.WORKSPACES.get('w'),
      ENDPOINTS.SECRETS.delete('s'),
      ENDPOINTS.PLUGINS.enable('p'),
      ENDPOINTS.BROWSER.frames('r'),
    ];
    for (const url of urls) {
      expect(url).not.toContain(':');
      expect(url).not.toContain('undefined');
    }
  });
});
