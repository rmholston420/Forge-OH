import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PluginBridge } from '@/lib/plugins/bridge';
import { PluginEventType } from '@/lib/plugins/schemas';
import { createHmac } from 'crypto';

const TEST_MANIFEST = {
  id:           '550e8400-e29b-41d4-a716-446655440000',
  name:         'Rigpa-LMS',
  version:      '1.0.0',
  baseUrl:      'https://rigpa.example.com',
  authType:     'bearer' as const,
  secret:       'test-secret-key',
  capabilities: [PluginEventType.RUN_STARTED, PluginEventType.APPROVAL_REQUIRED],
};

describe('PluginBridge', () => {
  let bridge: PluginBridge;

  beforeEach(() => {
    bridge = new PluginBridge();
    bridge.register(TEST_MANIFEST);
  });

  it('registers and lists manifests', () => {
    expect(bridge.list()).toHaveLength(1);
    expect(bridge.list()[0].name).toBe('Rigpa-LMS');
  });

  it('dispatches event only to plugins with matching capability', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200 })
    );
    const results = await bridge.dispatch(PluginEventType.RUN_STARTED, { runId: 'r1' });
    expect(results).toHaveLength(1);
    expect(results[0].ok).toBe(true);
    expect(fetchSpy).toHaveBeenCalledWith(
      'https://rigpa.example.com/events',
      expect.objectContaining({ method: 'POST' })
    );
    fetchSpy.mockRestore();
  });

  it('skips dispatch for events not in capabilities', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200 })
    );
    const results = await bridge.dispatch(PluginEventType.WORKSPACE_READY, {});
    expect(results).toHaveLength(0); // not in capabilities
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it('verifies HMAC signature on inbound webhook', () => {
    const handler = vi.fn();
    bridge.on(PluginEventType.RUN_STARTED, handler);

    const event = JSON.stringify({
      id: '550e8400-e29b-41d4-a716-446655440001',
      source: 'rigpa-lms',
      type: PluginEventType.RUN_STARTED,
      payload: { runId: 'r1' },
      timestamp: new Date().toISOString(),
    });
    const sig = createHmac('sha256', 'test-secret-key').update(event).digest('hex');
    const result = bridge.handleInbound(TEST_MANIFEST.id, event, sig);
    expect(result).not.toBeNull();
    expect(handler).toHaveBeenCalledOnce();
  });

  it('rejects inbound webhook with bad signature', () => {
    const event = JSON.stringify({ id: 'x', source: 'rigpa', type: PluginEventType.RUN_STARTED,
      payload: {}, timestamp: new Date().toISOString() });
    const result = bridge.handleInbound(TEST_MANIFEST.id, event, 'bad-sig');
    expect(result).toBeNull();
  });
});
