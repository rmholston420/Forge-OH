/**
 * plugin-bridge-edge-cases.test.ts
 *
 * Targets the paths NOT covered by the existing plugin-bridge.test.ts:
 *   - handleInbound with no secret (signature check bypassed)
 *   - handleInbound with wrong signature (rejected)
 *   - handleInbound with malformed JSON body (returns null)
 *   - on() listener off-function removes only the specific handler
 *   - dispatch targets only plugins that subscribe to the event type
 *   - dispatch with a plugin that has no capabilities sends nothing
 *   - _send bearer vs api_key auth header selection (via fetch mock)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createHmac } from 'crypto';
import { PluginBridge } from '@/lib/plugins/bridge';
import { PluginEventType } from '@/lib/plugins/schemas';

const BASE_MANIFEST = {
  id: '00000000-0000-0000-0000-000000000001',
  name: 'Test Plugin',
  version: '1.0.0',
  baseUrl: 'https://plugin.example.com',
  authType: 'none' as const,
  capabilities: [PluginEventType.RUN_STARTED],
};

const MANIFEST_NO_CAPS = {
  ...BASE_MANIFEST,
  id: '00000000-0000-0000-0000-000000000002',
  capabilities: [],
};

function makeEvent(overrides: Record<string, unknown> = {}) {
  return JSON.stringify({
    id: '00000000-0000-0000-0000-000000000099',
    source: 'forge-oh',
    type: PluginEventType.RUN_STARTED,
    payload: {},
    timestamp: new Date().toISOString(),
    ...overrides,
  });
}

function sign(secret: string, body: string) {
  return createHmac('sha256', secret).update(body).digest('hex');
}

let bridge: PluginBridge;

beforeEach(() => {
  bridge = new PluginBridge();
  vi.restoreAllMocks();
});

describe('handleInbound — no secret configured', () => {
  it('accepts any signature when plugin has no secret', () => {
    bridge.register(BASE_MANIFEST);
    const body = makeEvent();
    const result = bridge.handleInbound(BASE_MANIFEST.id, body, 'any-sig');
    expect(result).not.toBeNull();
    expect(result?.type).toBe(PluginEventType.RUN_STARTED);
  });
});

describe('handleInbound — wrong signature', () => {
  it('returns null when HMAC does not match', () => {
    const withSecret = { ...BASE_MANIFEST, secret: 'correct-secret' };
    bridge.register(withSecret);
    const body = makeEvent();
    const result = bridge.handleInbound(withSecret.id, body, 'wrong-sig');
    expect(result).toBeNull();
  });

  it('accepts the correct HMAC signature', () => {
    const secret = 'my-secret';
    const withSecret = { ...BASE_MANIFEST, secret };
    bridge.register(withSecret);
    const body = makeEvent();
    const sig = sign(secret, body);
    const result = bridge.handleInbound(withSecret.id, body, sig);
    expect(result).not.toBeNull();
  });
});

describe('handleInbound — malformed body', () => {
  it('returns null for invalid JSON', () => {
    bridge.register(BASE_MANIFEST);
    const result = bridge.handleInbound(BASE_MANIFEST.id, '{not json}', '');
    expect(result).toBeNull();
  });

  it('returns null when body fails PluginEventSchema validation', () => {
    bridge.register(BASE_MANIFEST);
    const body = JSON.stringify({ invalid: true });
    const result = bridge.handleInbound(BASE_MANIFEST.id, body, '');
    expect(result).toBeNull();
  });
});

describe('handleInbound — unknown plugin id', () => {
  it('returns null for unregistered plugin', () => {
    const result = bridge.handleInbound('00000000-0000-0000-0000-000000000099', makeEvent(), '');
    expect(result).toBeNull();
  });
});

describe('on() — listener management', () => {
  it('calls the handler when an inbound event of that type arrives', () => {
    bridge.register(BASE_MANIFEST);
    const handler = vi.fn();
    bridge.on(PluginEventType.RUN_STARTED, handler);
    const body = makeEvent();
    bridge.handleInbound(BASE_MANIFEST.id, body, '');
    expect(handler).toHaveBeenCalledOnce();
  });

  it('off function removes only the specific handler', () => {
    bridge.register(BASE_MANIFEST);
    const h1 = vi.fn();
    const h2 = vi.fn();
    const off1 = bridge.on(PluginEventType.RUN_STARTED, h1);
    bridge.on(PluginEventType.RUN_STARTED, h2);
    off1();
    bridge.handleInbound(BASE_MANIFEST.id, makeEvent(), '');
    expect(h1).not.toHaveBeenCalled();
    expect(h2).toHaveBeenCalledOnce();
  });

  it('calling off twice is safe (no-op on second call)', () => {
    bridge.register(BASE_MANIFEST);
    const h = vi.fn();
    const off = bridge.on(PluginEventType.RUN_STARTED, h);
    off();
    off();
    bridge.handleInbound(BASE_MANIFEST.id, makeEvent(), '');
    expect(h).not.toHaveBeenCalled();
  });
});

describe('dispatch — capability filtering', () => {
  it('sends only to plugins that subscribe to the event type', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);

    bridge.register(BASE_MANIFEST);       // subscribes to RUN_STARTED
    bridge.register(MANIFEST_NO_CAPS);    // subscribes to nothing

    const results = await bridge.dispatch(PluginEventType.RUN_STARTED, { foo: 'bar' });
    expect(results).toHaveLength(1);
    expect(results[0].pluginId).toBe(BASE_MANIFEST.id);
    expect(results[0].ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('returns empty array when no plugin subscribes to the event type', async () => {
    bridge.register(MANIFEST_NO_CAPS);
    const results = await bridge.dispatch(PluginEventType.RUN_COMPLETED, {});
    expect(results).toHaveLength(0);
  });
});

describe('dispatch — auth headers', () => {
  it('sets Authorization: Bearer header for authType bearer', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);
    const m = { ...BASE_MANIFEST, authType: 'bearer' as const, secret: 'tok' };
    bridge.register(m);
    await bridge.dispatch(PluginEventType.RUN_STARTED, {});
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({ 'Authorization': 'Bearer tok' });
  });

  it('sets X-API-Key header for authType api_key', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);
    const m = { ...BASE_MANIFEST, authType: 'api_key' as const, secret: 'apikey123' };
    bridge.register(m);
    await bridge.dispatch(PluginEventType.RUN_STARTED, {});
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toMatchObject({ 'X-API-Key': 'apikey123' });
  });

  it('includes X-Forge-Signature when plugin has a secret', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal('fetch', fetchMock);
    const m = { ...BASE_MANIFEST, secret: 'sigkey' };
    bridge.register(m);
    await bridge.dispatch(PluginEventType.RUN_STARTED, {});
    const [, init] = fetchMock.mock.calls[0];
    expect((init as RequestInit).headers).toHaveProperty('X-Forge-Signature');
  });

  it('returns ok:false with error string on fetch rejection', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));
    bridge.register(BASE_MANIFEST);
    const [result] = await bridge.dispatch(PluginEventType.RUN_STARTED, {});
    expect(result.ok).toBe(false);
    expect(result.error).toMatch('Network error');
  });
});
