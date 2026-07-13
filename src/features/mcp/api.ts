import { apiClient } from '@/lib/api/client';
import {
  MCPServerListSchema,
  MCPServerSchema,
  PluginListSchema,
  PluginSchema,
  PingResponseSchema,
} from './schemas';
import type { MCPServer, Plugin, PingResponse } from './schemas';

// MCP Servers
export async function fetchMCPServers(): Promise<MCPServer[]> {
  const data = await apiClient.get('/mcp');
  return MCPServerListSchema.parse(data);
}

export async function toggleMCPServer(
  id: string,
  enable: boolean,
): Promise<MCPServer> {
  const data = await apiClient.post(`/mcp/${id}/${enable ? 'enable' : 'disable'}`, {});
  return MCPServerSchema.parse(data);
}

export async function pingMCPServer(id: string): Promise<PingResponse> {
  const data = await apiClient.post(`/mcp/${id}/ping`, {});
  return PingResponseSchema.parse(data);
}

// Plugins
export async function fetchPlugins(): Promise<Plugin[]> {
  const data = await apiClient.get('/plugins');
  return PluginListSchema.parse(data);
}

export async function enablePlugin(id: string): Promise<Plugin> {
  const data = await apiClient.post(`/plugins/${id}/enable`, {});
  return PluginSchema.parse(data);
}

export async function disablePlugin(id: string): Promise<Plugin> {
  const data = await apiClient.post(`/plugins/${id}/disable`, {});
  return PluginSchema.parse(data);
}

export async function savePluginConfig(
  id: string,
  config: Record<string, unknown>,
): Promise<Plugin> {
  const data = await apiClient.post(`/plugins/${id}/config`, config);
  return PluginSchema.parse(data);
}
