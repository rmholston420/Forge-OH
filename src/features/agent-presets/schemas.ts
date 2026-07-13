import { z } from 'zod';

export const ModelIdSchema = z.enum([
  'gpt-4o',
  'claude-opus-4',
  'gemini-2.5-pro',
  'local-llama',
]);
export type ModelId = z.infer<typeof ModelIdSchema>;

export const LoopGuardConfigSchema = z.object({
  enabled:    z.boolean().default(true),
  windowSize: z.number().int().min(5).max(100).default(20),
  threshold:  z.number().int().min(1).default(3),
});

export const AgentPresetSchema = z.object({
  id:           z.string(),
  name:         z.string().min(1).max(64),
  description:  z.string().max(256).optional(),
  systemPrompt: z.string().max(32_000).default(''),
  model:        ModelIdSchema,
  maxSteps:     z.number().int().min(1).max(500).default(100),
  maxCost:      z.number().min(0).max(999).default(5.0),
  temperature:  z.number().min(0).max(2).default(0.2),
  topP:         z.number().min(0).max(1).default(0.95),
  toolAllowlist: z.array(z.string()).default([]),
  loopGuard:    LoopGuardConfigSchema.default({}),
  isDefault:    z.boolean().default(false),
  createdAt:    z.string().datetime(),
  updatedAt:    z.string().datetime(),
});
export type AgentPreset = z.infer<typeof AgentPresetSchema>;

export const CreateAgentPresetSchema = AgentPresetSchema.omit({
  id: true, createdAt: true, updatedAt: true, isDefault: true,
});
export type CreateAgentPresetRequest = z.infer<typeof CreateAgentPresetSchema>;

export const UpdateAgentPresetSchema = CreateAgentPresetSchema.partial();
export type UpdateAgentPresetRequest = z.infer<typeof UpdateAgentPresetSchema>;
