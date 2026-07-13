import { PluginManifestSchema, PluginEventSchema } from './schemas';
import type { PluginManifest, PluginEvent, PluginEventType } from './schemas';
import { createHmac, randomUUID } from 'crypto';

type DispatchResult = { pluginId: string; ok: boolean; status?: number; error?: string };

export class PluginBridge {
  private manifests = new Map<string, PluginManifest>();
  private inboundHandlers = new Map<string, ((event: PluginEvent) => void)[]>();

  register(manifest: PluginManifest): void {
    const parsed = PluginManifestSchema.parse(manifest);
    this.manifests.set(parsed.id, parsed);
  }

  unregister(id: string): void {
    this.manifests.delete(id);
  }

  list(): PluginManifest[] {
    return Array.from(this.manifests.values());
  }

  /** Dispatch an outbound event to all registered plugins that subscribe to it */
  async dispatch(
    type: PluginEventType,
    payload: Record<string, unknown>,
    meta: { runId?: string; workspaceId?: string } = {},
  ): Promise<DispatchResult[]> {
    const event: PluginEvent = PluginEventSchema.parse({
      id:          randomUUID(),
      source:      'forge-oh',
      type,
      payload,
      runId:       meta.runId,
      workspaceId: meta.workspaceId,
      timestamp:   new Date().toISOString(),
    });

    const targets = Array.from(this.manifests.values()).filter(p =>
      p.capabilities.includes(type)
    );

    return Promise.all(targets.map(plugin => this._send(plugin, event)));
  }

  /** Verify and handle an inbound webhook from a plugin */
  handleInbound(pluginId: string, rawBody: string, signature: string): PluginEvent | null {
    const plugin = this.manifests.get(pluginId);
    if (!plugin) return null;

    if (plugin.secret) {
      const expected = createHmac('sha256', plugin.secret)
        .update(rawBody)
        .digest('hex');
      if (expected !== signature) return null; // reject invalid signature
    }

    try {
      const event = PluginEventSchema.parse(JSON.parse(rawBody));
      const handlers = this.inboundHandlers.get(event.type) ?? [];
      handlers.forEach(h => h(event));
      return event;
    } catch { return null; }
  }

  on(type: PluginEventType, handler: (event: PluginEvent) => void): () => void {
    const handlers = this.inboundHandlers.get(type) ?? [];
    handlers.push(handler);
    this.inboundHandlers.set(type, handlers);
    return () => {
      const updated = (this.inboundHandlers.get(type) ?? []).filter(h => h !== handler);
      this.inboundHandlers.set(type, updated);
    };
  }

  private async _send(plugin: PluginManifest, event: PluginEvent): Promise<DispatchResult> {
    try {
      const body = JSON.stringify(event);
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };

      if (plugin.authType === 'bearer' && plugin.secret) {
        headers['Authorization'] = `Bearer ${plugin.secret}`;
      } else if (plugin.authType === 'api_key' && plugin.secret) {
        headers['X-API-Key'] = plugin.secret;
      }

      if (plugin.secret) {
        const sig = createHmac('sha256', plugin.secret).update(body).digest('hex');
        headers['X-Forge-Signature'] = sig;
      }

      const res = await fetch(`${plugin.baseUrl}/events`, {
        method: 'POST', headers, body,
        signal: AbortSignal.timeout(5000),
      });
      return { pluginId: plugin.id, ok: res.ok, status: res.status };
    } catch (err) {
      return { pluginId: plugin.id, ok: false, error: String(err) };
    }
  }
}

// Singleton
export const pluginBridge = new PluginBridge();
