import { z } from 'zod';

export const ThemeSchema = z.enum(['system', 'light', 'dark']);
export const FontSizeSchema = z.enum(['sm', 'md', 'lg']);
export const AccentColorSchema = z.enum([
  'teal', 'blue', 'purple', 'orange', 'gold', 'green',
]);

export const KeyboardShortcutsSchema = z.record(
  z.string(), // action key e.g. 'newRun', 'commandPalette'
  z.string()  // key combo e.g. 'Ctrl+K', 'Shift+R'
);

export const SettingsSchema = z.object({
  theme: ThemeSchema.default('system'),
  accentColor: AccentColorSchema.default('teal'),
  fontSize: FontSizeSchema.default('md'),
  defaultModel: z.string().default('gpt-4o'),
  defaultAgentPreset: z.string().default('default'),
  maxConcurrentRuns: z.number().int().min(1).max(8).default(3),
  autoApprove: z.boolean().default(false),
  streamingEnabled: z.boolean().default(true),
  keyboardShortcuts: KeyboardShortcutsSchema.default({
    newRun: 'Shift+R',
    commandPalette: 'Ctrl+K',
    focusSearch: 'Ctrl+/',
    pauseRun: 'Shift+P',
    approveStep: 'Shift+A',
  }),
});

export type Settings = z.infer<typeof SettingsSchema>;
export type Theme = z.infer<typeof ThemeSchema>;
export type FontSize = z.infer<typeof FontSizeSchema>;
export type AccentColor = z.infer<typeof AccentColorSchema>;

export const UpdateSettingsRequestSchema = SettingsSchema.partial();
export type UpdateSettingsRequest = z.infer<typeof UpdateSettingsRequestSchema>;
