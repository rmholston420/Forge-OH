/**
 * plugin-schemas-inbound.test.ts
 *
 * Covers InboundCommandSchema discriminated union and PluginManifestSchema
 * validation edge cases not covered by plugin-bridge.test.ts.
 */
import { describe, it, expect } from 'vitest';
import {
  InboundCommandSchema,
  PluginManifestSchema,
  PluginEventSchema,
  PluginEventType,
} from '@/lib/plugins/schemas';

const VALID_MANIFEST = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'My Plugin',
  version: '1.2.3',
  baseUrl: 'https://plugin.example.com',
};

describe('PluginManifestSchema', () => {
  it('parses a minimal valid manifest (authType and capabilities default)', () => {
    const result = PluginManifestSchema.parse(VALID_MANIFEST);
    expect(result.authType).toBe('none');
    expect(result.capabilities).toEqual([]);
  });

  it('rejects a non-semver version string', () => {
    expect(() => PluginManifestSchema.parse({ ...VALID_MANIFEST, version: 'v1' })).toThrow();
  });

  it('rejects a non-URL baseUrl', () => {
    expect(() => PluginManifestSchema.parse({ ...VALID_MANIFEST, baseUrl: 'not-a-url' })).toThrow();
  });

  it('rejects a non-UUID id', () => {
    expect(() => PluginManifestSchema.parse({ ...VALID_MANIFEST, id: 'bad-id' })).toThrow();
  });

  it('rejects an empty name', () => {
    expect(() => PluginManifestSchema.parse({ ...VALID_MANIFEST, name: '' })).toThrow();
  });

  it('accepts all three authType values', () => {
    for (const authType of ['none', 'bearer', 'api_key'] as const) {
      expect(() => PluginManifestSchema.parse({ ...VALID_MANIFEST, authType })).not.toThrow();
    }
  });

  it('accepts capabilities array with valid event types', () => {
    const result = PluginManifestSchema.parse({
      ...VALID_MANIFEST,
      capabilities: [PluginEventType.RUN_STARTED, PluginEventType.ARTIFACT_READY],
    });
    expect(result.capabilities).toHaveLength(2);
  });
});

describe('InboundCommandSchema — discriminated union', () => {
  it('parses approve_run', () => {
    const result = InboundCommandSchema.parse({ command: 'approve_run', runId: 'run-1' });
    expect(result.command).toBe('approve_run');
  });

  it('parses stop_run', () => {
    const result = InboundCommandSchema.parse({ command: 'stop_run', runId: 'run-2' });
    expect(result.command).toBe('stop_run');
  });

  it('parses create_run', () => {
    const result = InboundCommandSchema.parse({
      command: 'create_run',
      agentPreset: 'default',
      workspaceId: 'ws-1',
    });
    expect(result.command).toBe('create_run');
  });

  it('rejects unknown command', () => {
    expect(() => InboundCommandSchema.parse({ command: 'unknown_cmd' })).toThrow();
  });

  it('rejects approve_run without runId', () => {
    expect(() => InboundCommandSchema.parse({ command: 'approve_run' })).toThrow();
  });

  it('rejects create_run without workspaceId', () => {
    expect(() =>
      InboundCommandSchema.parse({ command: 'create_run', agentPreset: 'default' })
    ).toThrow();
  });
});

describe('PluginEventSchema', () => {
  const VALID_EVENT = {
    id: '00000000-0000-0000-0000-000000000099',
    source: 'forge-oh',
    type: PluginEventType.RUN_COMPLETED,
    payload: {},
    timestamp: new Date().toISOString(),
  };

  it('parses a valid event', () => {
    expect(() => PluginEventSchema.parse(VALID_EVENT)).not.toThrow();
  });

  it('accepts all eight event types', () => {
    for (const type of Object.values(PluginEventType)) {
      expect(() => PluginEventSchema.parse({ ...VALID_EVENT, type })).not.toThrow();
    }
  });

  it('rejects an unknown event type', () => {
    expect(() => PluginEventSchema.parse({ ...VALID_EVENT, type: 'unknown' })).toThrow();
  });

  it('runId and workspaceId are optional', () => {
    const result = PluginEventSchema.parse(VALID_EVENT);
    expect(result.runId).toBeUndefined();
    expect(result.workspaceId).toBeUndefined();
  });

  it('accepts runId and workspaceId when provided', () => {
    const result = PluginEventSchema.parse({ ...VALID_EVENT, runId: 'r1', workspaceId: 'ws1' });
    expect(result.runId).toBe('r1');
    expect(result.workspaceId).toBe('ws1');
  });
});
