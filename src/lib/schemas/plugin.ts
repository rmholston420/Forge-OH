import { z } from 'zod';

export const PluginStatusSchema = z.enum(['enabled', 'disabled', 'error', 'installing']);
export type PluginStatus = z.infer<typeof PluginStatusSchema>;

export const PluginTransportSchema = z.enum(['stdio', 'sse', 'http']);
export type PluginTransport = z.infer<typeof PluginTransportSchema>;

/**
 * Plugin (aka MCP server registration) shape. Aligned with what
 * `GET /api/mcp` and `GET /api/plugins` return from the BFF.
 * See bff/routers/mcp.py for authoritative field list.
 */
export const PluginSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string().default('0.0.0'),
  description: z.string().optional(),
  author: z.string().optional(),
  status: PluginStatusSchema,
  transport: PluginTransportSchema,
  capabilities: z.array(z.string()).default([]),
  toolCount: z.number().default(0),
  command: z.string().optional(),
  args: z.array(z.string()).optional(),
  url: z.string().optional(),
  configSchema: z.record(z.string(), z.unknown()).optional(),
  installedAt: z.string().optional(),
  updatedAt: z.string().optional(),
});

export type Plugin = z.infer<typeof PluginSchema>;

export const PluginListResponseSchema = z.object({
  plugins: z.array(PluginSchema),
  total: z.number(),
});

export type PluginListResponse = z.infer<typeof PluginListResponseSchema>;

export const InstallPluginSchema = z.object({
  name: z.string(),
  transport: PluginTransportSchema,
  command: z.string().optional(),
  args: z.array(z.string()).optional(),
  url: z.string().optional(),
  description: z.string().optional(),
});

export type InstallPlugin = z.infer<typeof InstallPluginSchema>;
