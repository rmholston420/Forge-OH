import crypto from 'node:crypto';
import { PluginEventSchema, type PluginEvent, type PluginManifest, PluginEventType, PluginManifestSchema } from './schemas';

type Handler = (event: PluginEvent) => void;

type DispatchResult = {
  pluginId: string;
  ok: boolean;
  status?: number;
  error?: string;
};

export class PluginBridge {
  private manifests = new Map<string, PluginManifest>();
  private handlers = new Map<PluginEventType, Set<Handler>>();

  register(manifest: PluginManifest): void {
    const parsed = PluginManifestSchema.parse(manifest);
    this.manifests.set(parsed.id, parsed);
  }

  on(type: PluginEventType, handler: Handler): () => void {
    const bucket = this.handlers.get(type) ?? new Set<Handler>();
    bucket.add(handler);
    this.handlers.set(type, bucket);

    let removed = false;
    return () => {
      if (removed) return;
      removed = true;
      const current = this.handlers.get(type);
      current?.delete(handler);
      if (current && current.size === 0) this.handlers.delete(type);
    };
  }

  handleInbound(pluginId: string, body: string, signature?: string): PluginEvent | null {
    const manifest = this.manifests.get(pluginId);
    if (!manifest) return null;

    if (manifest.secret) {
      const expected = crypto.createHmac('sha256', manifest.secret).update(body).digest('hex');
      if (signature !== expected) return null;
    }

    let json: unknown;
    try {
      json = JSON.parse(body);
    } catch {
      return null;
    }

    const parsed = PluginEventSchema.safeParse(json);
    if (!parsed.success) return null;

    const event = parsed.data;
    const bucket = this.handlers.get(event.type);
    if (bucket) {
      for (const handler of bucket) handler(event);
    }
    return event;
  }

  async dispatch(type: PluginEventType, payload: Record<string, unknown>): Promise<DispatchResult[]> {
    const results: DispatchResult[] = [];
    const event = {
      type,
      payload,
    };

    for (const manifest of this.manifests.values()) {
      if (!manifest.capabilities.includes(type)) continue;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (manifest.authType === 'bearer' && manifest.secret) headers.Authorization = `Bearer ${manifest.secret}`;
      if (manifest.authType === 'api_key' && manifest.secret) headers['X-API-Key'] = manifest.secret;

      const body = JSON.stringify(event);

      if (manifest.secret) {
        headers['X-Forge-Signature'] = crypto.createHmac('sha256', manifest.secret).update(body).digest('hex');
      }

      try {
        const response = await fetch(manifest.baseUrl, {
          method: 'POST',
          headers,
          body,
        });
        results.push({
          pluginId: manifest.id,
          ok: response.ok,
          status: response.status,
        });
      } catch (error) {
        results.push({
          pluginId: manifest.id,
          ok: false,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    return results;
  }
}
