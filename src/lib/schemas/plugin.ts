import { z } from 'zod';

export const PluginStatusSchema = z.enum(['enabled', 'disabled', 'error', 'installing']);
export type PluginStatus = z.infer<typeof PluginStatusSchema>;

export const PluginSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  author: z.string().optional(),
  status: PluginStatusSchema,
  configSchema: z.record(z.unknown()).optional(),
  installedAt: z.string().datetime().optional(),
  updatedAt: z.string().datetime(),
});

export type Plugin = z.infer<typeof PluginSchema>;

export const PluginListResponseSchema = z.object({
  plugins: z.array(PluginSchema),
  total: z.number(),
});

export type PluginListResponse = z.infer<typeof PluginListResponseSchema>;
