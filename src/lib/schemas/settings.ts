import { z } from 'zod';

export const ThemeSchema = z.enum(['light', 'dark', 'system']);
export const AccentColorSchema = z.enum(['teal', 'blue', 'purple', 'green', 'amber', 'red']);
export const FontSizeSchema = z.enum(['sm', 'md', 'lg']);

export const KeyboardShortcutsSchema = z.record(z.string(), z.string()).default({
  commandPalette: 'Mod+K',
  newRun: 'Mod+N',
  focusSearch: '/',
});

export const SettingsSchema = z.object({
  theme: ThemeSchema.default('system'),
  language: z.string().default('en'),
  accentColor: AccentColorSchema.default('teal'),
  fontSize: FontSizeSchema.default('md'),
  defaultModel: z.string().default(''),
  defaultAgentPreset: z.string().default(''),
  maxConcurrentRuns: z.number().int().min(1).max(8).default(2),
  autoApprove: z.boolean().default(false),
  streamingEnabled: z.boolean().default(true),
  keyboardShortcuts: KeyboardShortcutsSchema,
}).passthrough();

export const AppSettingsSchema = SettingsSchema;
export const UpdateSettingsRequestSchema = SettingsSchema.partial();

export type Settings = z.infer<typeof SettingsSchema>;
export type AppSettings = z.infer<typeof AppSettingsSchema>;
export type UpdateSettingsRequest = z.infer<typeof UpdateSettingsRequestSchema>;
