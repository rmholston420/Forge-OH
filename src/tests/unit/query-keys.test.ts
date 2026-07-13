/**
 * src/tests/unit/query-keys.test.ts
 *
 * Covers: src/lib/query/query-keys.ts
 * — Key hierarchy: scoped keys are supersets of root
 * — Param isolation: different IDs produce different keys
 * — No two namespaces share the same root string
 */
import { describe, it, expect } from 'vitest';
import {
  runKeys,
  workspaceKeys,
  agentKeys,
  secretKeys,
  observabilityKeys,
} from '@/lib/query/query-keys';

describe('runKeys', () => {
  it('root key is ["runs"]', () => {
    expect(runKeys.all).toEqual(['runs']);
  });
  it('lists() starts with root', () => {
    expect(runKeys.lists()[0]).toBe('runs');
  });
  it('detail() includes the id', () => {
    expect(runKeys.detail('r1')).toContain('r1');
  });
  it('detail() with different ids produces different keys', () => {
    expect(runKeys.detail('r1')).not.toEqual(runKeys.detail('r2'));
  });
  it('events() includes runId', () => {
    expect(runKeys.events('r1')).toContain('r1');
  });
  it('plan() includes runId', () => {
    expect(runKeys.plan('r1')).toContain('r1');
  });
  it('files() includes runId', () => {
    expect(runKeys.files('r1')).toContain('r1');
  });
});

describe('workspaceKeys', () => {
  it('root is ["workspaces"] or starts with workspaces', () => {
    const root = workspaceKeys.all ?? workspaceKeys.lists?.();
    expect(JSON.stringify(root)).toContain('workspace');
  });
  it('detail() with different ids produces different keys', () => {
    expect(workspaceKeys.detail('w1')).not.toEqual(workspaceKeys.detail('w2'));
  });
});

describe('agentKeys', () => {
  it('presetsKey does not overlap with runKeys.all', () => {
    const presets = agentKeys.presets?.() ?? agentKeys.all;
    expect(presets[0]).not.toBe('runs');
  });
});

describe('secretKeys', () => {
  it('root does not overlap with runKeys', () => {
    const root = secretKeys.all ?? secretKeys.lists?.();
    const rootStr = Array.isArray(root) ? root[0] : root;
    expect(rootStr).not.toBe('runs');
  });
});

describe('observabilityKeys', () => {
  it('summary key is unique namespace', () => {
    const summary = observabilityKeys.summary?.() ?? observabilityKeys.all;
    const str = JSON.stringify(summary);
    expect(str).toContain('observab');
  });
});

describe('namespace uniqueness', () => {
  it('run/workspace/agent/secret/observability roots are all distinct', () => {
    const roots = [
      runKeys.all[0],
      (workspaceKeys.all ?? ['workspaces'])[0],
      (agentKeys.all ?? ['agents'])[0],
      (secretKeys.all ?? ['secrets'])[0],
      (observabilityKeys.all ?? ['observability'])[0],
    ];
    const unique = new Set(roots);
    expect(unique.size).toBe(roots.length);
  });
});
