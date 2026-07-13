import { z } from 'zod';

export const PluginStatusSchema = z.enum([
  'installed',
  'enabled',
  'disabled',
  'update_available',
  'error',
]);

export const PluginSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().optional(),
  version: z.string(),
  status: PluginStatusSchema,
  author: z.string().optional(),
  homepage: z.string().url().optional(),
  installedAt: z.string().datetime().optional(),
});

export type Plugin = z.infer<typeof PluginSchema>;

export const PluginListSchema = z.array(PluginSchema);
export type PluginList = z.infer<typeof PluginListSchema>;
