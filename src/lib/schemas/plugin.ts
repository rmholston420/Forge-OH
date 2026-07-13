import { z } from 'zod';

export const PluginTransportSchema = z.enum(['stdio', 'sse', 'http']);

export const PluginStatusSchema = z.enum(['enabled', 'disabled', 'error', 'installing']);

export const PluginCapabilitySchema = z.enum([
  'tools', 'resources', 'prompts', 'sampling',
]);

export const PluginSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().nullable().default(null),
  author: z.string().nullable().default(null),
  transport: PluginTransportSchema,
  status: PluginStatusSchema,
  capabilities: z.array(PluginCapabilitySchema).default([]),
  command: z.string().nullable().default(null),   // stdio: command to exec
  url: z.string().nullable().default(null),        // sse/http: endpoint url
  envVars: z.record(z.string(), z.string()).default({}),
  toolCount: z.number().int().min(0).default(0),
  installedAt: z.string().nullable().default(null),
  lastHeartbeatAt: z.string().nullable().default(null),
});

export const InstallPluginSchema = z.object({
  name: z.string().min(1),
  version: z.string().default('latest'),
  transport: PluginTransportSchema,
  command: z.string().nullable().optional(),
  url: z.string().url().nullable().optional(),
  envVars: z.record(z.string(), z.string()).default({}),
});

export type Plugin = z.infer<typeof PluginSchema>;
export type PluginTransport = z.infer<typeof PluginTransportSchema>;
export type PluginStatus = z.infer<typeof PluginStatusSchema>;
export type InstallPlugin = z.infer<typeof InstallPluginSchema>;
