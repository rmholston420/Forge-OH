/**
 * src/tests/unit/lib-query-keys.test.ts
 *
 * Query keys are the identity of every TanStack cache entry — assert the
 * shape/order of every factory so a rename in one place doesn't silently
 * invalidate a different cache.
 */
import { describe, it, expect } from 'vitest';
import {
  runKeys,
  agentKeys,
  workspaceKeys,
  secretKeys,
  settingsKeys,
  notificationKeys,
  observabilityKeys,
  QUERY_KEYS,
} from '@/lib/query/query-keys';

describe('runKeys', () => {
  it('all + lists shape', () => {
    expect(runKeys.all).toEqual(['runs']);
    expect(runKeys.lists()).toEqual(['runs', 'list']);
  });
  it('list defaults to empty object when no filter', () => {
    expect(runKeys.list()).toEqual(['runs', 'list', {}]);
    expect(runKeys.list({ status: 'running' })).toEqual(['runs', 'list', { status: 'running' }]);
  });
  it('per-run factories carry runId', () => {
    expect(runKeys.detail('r1')).toEqual(['runs', 'r1']);
    expect(runKeys.events('r1')).toEqual(['runs', 'r1', 'events']);
    expect(runKeys.plan('r1')).toEqual(['runs', 'r1', 'plan']);
    expect(runKeys.files('r1')).toEqual(['runs', 'r1', 'files']);
    expect(runKeys.artifacts('r1')).toEqual(['runs', 'r1', 'artifacts']);
    expect(runKeys.commands('r1')).toEqual(['runs', 'r1', 'commands']);
    expect(runKeys.traces('r1')).toEqual(['runs', 'r1', 'traces']);
  });
  it('presets is a top-level runs child', () => {
    expect(runKeys.presets()).toEqual(['runs', 'presets']);
  });
});

describe('agentKeys / workspaceKeys / secretKeys', () => {
  it('agentKeys', () => {
    expect(agentKeys.all).toEqual(['agents']);
    expect(agentKeys.presets()).toEqual(['agents', 'presets']);
    expect(agentKeys.detail('p-1')).toEqual(['agents', 'p-1']);
  });
  it('workspaceKeys', () => {
    expect(workspaceKeys.all).toEqual(['workspaces']);
    expect(workspaceKeys.lists()).toEqual(['workspaces', 'list']);
    expect(workspaceKeys.list()).toEqual(['workspaces', 'list', {}]);
    expect(workspaceKeys.detail('ws-1')).toEqual(['workspaces', 'ws-1']);
  });
  it('secretKeys', () => {
    expect(secretKeys.all).toEqual(['secrets']);
    expect(secretKeys.lists()).toEqual(['secrets', 'list']);
    expect(secretKeys.list({ scope: 'global' })).toEqual(['secrets', 'list', { scope: 'global' }]);
    expect(secretKeys.detail('sec-1')).toEqual(['secrets', 'sec-1']);
  });
});

describe('settings / notifications / observability keys', () => {
  it('settings', () => {
    expect(settingsKeys.all).toEqual(['settings']);
    expect(settingsKeys.current()).toEqual(['settings', 'current']);
  });
  it('notifications', () => {
    expect(notificationKeys.all).toEqual(['notifications']);
    expect(notificationKeys.list()).toEqual(['notifications', 'list']);
  });
  it('observability with and without filter', () => {
    expect(observabilityKeys.all).toEqual(['observability']);
    expect(observabilityKeys.summary()).toEqual(['observability', {}]);
    expect(observabilityKeys.summary({ range: '7d' })).toEqual([
      'observability', { range: '7d' },
    ]);
  });
});

describe('QUERY_KEYS namespace', () => {
  it('exposes canonical + legacy aliases', () => {
    expect(QUERY_KEYS.runs).toBe(runKeys);
    expect(QUERY_KEYS.runKeys).toBe(runKeys);
    expect(QUERY_KEYS.workspaces).toBe(workspaceKeys);
    expect(QUERY_KEYS.workspaceKeys).toBe(workspaceKeys);
    expect(QUERY_KEYS.secrets).toBe(secretKeys);
    expect(QUERY_KEYS.secretKeys).toBe(secretKeys);
    expect(QUERY_KEYS.observability).toBe(observabilityKeys);
    expect(QUERY_KEYS.observabilityKeys).toBe(observabilityKeys);
  });
  it('plugins + mcp inline keys are stable', () => {
    expect(QUERY_KEYS.plugins.all).toEqual(['plugins']);
    expect(QUERY_KEYS.plugins.detail('p1')).toEqual(['plugins', 'p1']);
    expect(QUERY_KEYS.mcp.all).toEqual(['mcp']);
    expect(QUERY_KEYS.mcp.detail('srv-1')).toEqual(['mcp', 'srv-1']);
  });
});
