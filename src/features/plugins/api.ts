/**
 * src/features/plugins/api.ts
 *
 * All BFF calls for the Plugins feature.
 * Uses bffGet/bffPost/bffDelete from lib/api/client + ENDPOINTS registry.
 */
import { bffGet, bffPost, bffDelete } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import type { Plugin, InstallPlugin } from '@/lib/schemas/plugin';

export async function fetchPlugins(): Promise<Plugin[]> {
  const res = await bffGet<{ data: Plugin[] }>(ENDPOINTS.PLUGINS.list());
  return unwrap(res).data ?? [];
}

export interface MarketplacePlugin {
  id: string;
  name: string;
  description: string | null;
  source: string | null;
  installed: boolean;
  skills: string[];
}

export async function fetchMarketplacePlugins(): Promise<MarketplacePlugin[]> {
  const res = await bffGet<{ data: MarketplacePlugin[] }>(ENDPOINTS.PLUGINS.marketplace());
  return unwrap(res).data ?? [];
}

export async function installPlugin(body: InstallPlugin): Promise<Plugin> {
  const res = await bffPost<{ data: Plugin }>(ENDPOINTS.PLUGINS.create(), body);
  return unwrap(res).data;
}

/**
 * Install a marketplace plugin by source. Uses the dedicated
 * POST /api/plugins/install path which the BFF proxies straight through
 * to the agent-server marketplace installer.
 */
export async function installFromMarketplace(body: { source: string; ref?: string; force?: boolean }): Promise<Plugin> {
  const res = await bffPost<{ data: Plugin }>(ENDPOINTS.PLUGINS.install(), body);
  return unwrap(res).data;
}

export async function togglePlugin(id: string, enabled: boolean): Promise<Plugin> {
  const path = enabled ? ENDPOINTS.PLUGINS.enable(id) : ENDPOINTS.PLUGINS.disable(id);
  const res = await bffPost<{ data: Plugin }>(path, {});
  return unwrap(res).data;
}

export async function uninstallPlugin(id: string): Promise<void> {
  await bffDelete<{ ok: boolean }>(ENDPOINTS.PLUGINS.uninstall(id));
}

export async function pingPlugin(
  id: string,
): Promise<{ ok: boolean; latencyMs: number | null; toolCount?: number; error?: string }> {
  const res = await bffPost<{ ok: boolean; latencyMs: number | null; toolCount?: number; error?: string }>(
    ENDPOINTS.PLUGINS.ping(id),
    {},
  );
  return unwrap(res);
}
