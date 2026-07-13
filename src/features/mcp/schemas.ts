import { z } from 'zod';

export const MCPServerStatusSchema = z.enum([
  'connected',
  'connecting',
  'error',
  'disabled',
]);

export const MCPServerSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(80),
  url: z.string().url(),
  status: MCPServerStatusSchema,
  toolCount: z.number().int().nonnegative().default(0),
  lastPingMs: z.number().nullable().default(null),
  lastPingAt: z.string().datetime({ offset: true }).nullable().default(null),
  version: z.string().optional(),
  description: z.string().optional(),
});

export const MCPServerListSchema = z.array(MCPServerSchema);

export const PluginStatusSchema = z.enum([
  'enabled',
  'disabled',
  'error',
  'installing',
]);

// Minimal JSON-Schema-subset for plugin config fields
const ConfigFieldSchema = z.object({
  type: z.enum(['string', 'number', 'boolean', 'select']),
  label: z.string(),
  description: z.string().optional(),
  required: z.boolean().default(false),
  default: z.unknown().optional(),
  options: z.array(z.string()).optional(), // for select
});

export const PluginConfigSchemaShape = z.record(ConfigFieldSchema);

export const PluginSchema = z.object({
  id: z.string(),
  name: z.string().min(1).max(80),
  version: z.string(),
  status: PluginStatusSchema,
  description: z.string().optional(),
  author: z.string().optional(),
  installedAt: z.string().datetime({ offset: true }).nullable().default(null),
  configSchema: PluginConfigSchemaShape.optional(),
});

export const PluginListSchema = z.array(PluginSchema);

export const PingResponseSchema = z.object({
  serverId: z.string(),
  latencyMs: z.number(),
  pingAt: z.string().datetime({ offset: true }),
});

export type MCPServer = z.infer<typeof MCPServerSchema>;
export type MCPServerStatus = z.infer<typeof MCPServerStatusSchema>;
export type Plugin = z.infer<typeof PluginSchema>;
export type PluginStatus = z.infer<typeof PluginStatusSchema>;
export type PingResponse = z.infer<typeof PingResponseSchema>;
