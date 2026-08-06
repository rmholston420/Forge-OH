import { z } from 'zod';

// Stage 2.1 — model IDs were widened on the backend from a cloud-only Literal
// to a free-form string so local runtimes (vLLM, Ollama, llama.cpp, SGLang)
// can be named directly. Frontend mirrors that: any non-empty string is a
// legal model identifier. The `backendId` field carries the routing intent.
export const ModelIdSchema = z.string().min(1);
export type ModelId = z.infer<typeof ModelIdSchema>;

// Canonical inference-backend ids — must stay in sync with
// bff/services/inference_backends/registry.py::BACKEND_REGISTRY and
// bff/services/inference_backends/types.py::BackendKind.
export const BackendIdSchema = z.enum([
  'ollama',
  'vllm-coder',
  'vllm-planner',
  'vllm-legacy',
  'llamacpp',
  'sglang',
]);
export type BackendId = z.infer<typeof BackendIdSchema>;

// Role hint carried by a preset. Distinct from BFF `RoleRoute.role` (which
// is only "coder" | "planner"): here we allow `null` on the wire so a
// preset can decline to constrain the router.
export const RoleHintSchema = z.enum(['coder', 'planner']);
export type RoleHint = z.infer<typeof RoleHintSchema>;

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
  // Stage 2.1 additive fields. Both nullable on the wire so pre-Stage-2
  // presets (or presets created via API without them) still parse.
  backendId:    BackendIdSchema.nullish(),
  role:         RoleHintSchema.nullish(),
  maxSteps:     z.number().int().min(1).max(500).default(100),
  maxCost:      z.number().min(0).max(999).default(5.0),
  temperature:  z.number().min(0).max(2).default(0.2),
  topP:         z.number().min(0).max(1).default(0.95),
  toolAllowlist: z.array(z.string()).default([]),
  loopGuard:    LoopGuardConfigSchema.default({ enabled: true, windowSize: 20, threshold: 0.85 }),
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
