import { createHmac, timingSafeEqual } from 'crypto';
import { PluginEventSchema, PluginEventType, PluginManifestSchema } from '@/lib/plugins/schemas';

type PluginManifest = ReturnType<typeof PluginManifestSchema.parse>;
type PluginEvent = ReturnType<typeof PluginEventSchema.parse>;
type Handler = (event: PluginEvent) => void;

export class PluginBridge {
  private manifests = new Map<string, PluginManifest>();
  private handlers = new Map<string, Set<Handler>>();

  register(manifest: unknown): void {
    const parsed = PluginManifestSchema.parse(manifest);
    this.manifests.set(parsed.id, parsed);
  }

  list(): PluginManifest[] {
    return Array.from(this.manifests.values());
  }

  on(type: PluginEventType | string, handler: Handler): () => void {
    if (!this.handlers.has(type)) this.handlers.set(type, new Set());
    this.handlers.get(type)!.add(handler);
    let removed = false;
    return () => {
      if (removed) return;
      removed = true;
      this.off(type, handler);
    };
  }

  off(type: PluginEventType | string, handler: Handler): void {
    this.handlers.get(type)?.delete(handler);
  }

  async dispatch(type: PluginEventType, payload: Record<string, unknown>) {
    const matched = this.list().filter((m) => (m.capabilities ?? []).includes(type));
    if (matched.length === 0) return [];

    const body = JSON.stringify({ type, payload });
    const results = await Promise.all(
      matched.map(async (manifest) => {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (manifest.authType === 'bearer' && manifest.secret) {
          headers.Authorization = `Bearer ${manifest.secret}`;
          headers['X-Forge-Signature'] = createHmac('sha256', manifest.secret).update(body).digest('hex');
        } else if (manifest.authType === 'api_key' && manifest.secret) {
          headers['X-API-Key'] = manifest.secret;
        }

        const url = `${manifest.baseUrl.replace(/\/$/, '')}/events`;
        try {
          const response = await fetch(url, { method: 'POST', headers, body });
          return { ok: response.ok, status: response.status, pluginId: manifest.id };
        } catch (error) {
          return {
            ok: false,
            status: 0,
            pluginId: manifest.id,
            error: error instanceof Error ? error.message : String(error),
          };
        }
      }),
    );

    return results;
  }

  handleInbound(pluginId: string, rawEvent: string, signature?: string) {
    const manifest = this.manifests.get(pluginId);
    if (!manifest) return null;

    if (manifest.secret) {
      if (!signature) return null;
      const expected = createHmac('sha256', manifest.secret).update(rawEvent).digest('hex');
      const a = Buffer.from(signature);
      const b = Buffer.from(expected);
      if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
    }

    let parsedBody: unknown;
    try {
      parsedBody = JSON.parse(rawEvent);
    } catch {
      return null;
    }

    const parsed = PluginEventSchema.safeParse(parsedBody);
    if (!parsed.success) return null;

    const handlers = this.handlers.get(parsed.data.type);
    handlers?.forEach((handler) => handler(parsed.data));
    return parsed.data;
  }
}
