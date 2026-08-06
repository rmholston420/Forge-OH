import { z } from 'zod';

// ISO-8601 datetime — accepts both Z-suffix ("2026-07-13T00:00:00Z") and
// numeric offset ("2026-07-13T00:00:00+00:00"). z.string().datetime() rejects
// Z-suffix in some Zod versions, so we use a permissive regex instead.
const isoDatetime = z
  .string()
  .regex(
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/,
    'Expected ISO-8601 datetime string',
  );

export const RunStatusSchema = z.enum([
  'idle',
  'running',
  'streaming',
  'queued',
  'paused',
  // Canonical form: `awaiting_approval` (underscore) — matches BFF _STATUS_MAP
  // at bff/routers/runs.py:101 and Python/openhands-sdk convention. The
  // legacy dash spelling has been retired (see BUILD_LOG 2026-08-05
  // 23:5x EDT hygiene commit).
  'awaiting_approval',
  'disconnected',
  'succeeded',
  'failed',
  'blocked',
]);

export type RunStatus = z.infer<typeof RunStatusSchema>;

export const RunSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  status: RunStatusSchema,
  agentPresetName: z.string(),
  workspaceId: z.string(),
  workspaceType: z.enum(['local', 'docker', 'remote-api', 'remote_api']),
  activeTool: z.string().nullable(),
  updatedAt: isoDatetime,
  createdAt: isoDatetime,
  elapsedMs: z.number().nullable(),
  estimatedCostUsd: z.number().nullable(),
  selectedModel: z.string().nullable().optional(),
  routing: z.object({
    selected: z.string().nullable().optional(),
    reason: z.string().optional(),
  }).optional(),
});

export type RunSummary = z.infer<typeof RunSummarySchema>;

export const RunDetailSchema = RunSummarySchema.extend({
  taskPrompt: z.string(),
  modelName: z.string().optional(),
  contextTokens: z.number().optional(),
  totalEvents: z.number().optional(),
  totalArtifacts: z.number().optional(),
  totalCommands: z.number().optional(),
});

export type RunDetail = z.infer<typeof RunDetailSchema>;

// BFF list envelope: { data: [...], pageInfo: { total, page, pageSize } }
export const RunListResponseSchema = z.object({
  data: z.array(RunSummarySchema),
  pageInfo: z.object({
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type RunListResponse = z.infer<typeof RunListResponseSchema>;

// Canonical create-run request shape — aligns with BFF CreateRunRequest.
// Single source of truth: features/runs/schemas.ts re-exports this type.
// Stage 2.1 backend ids — mirrors bff/services/inference_backends/registry.py.
export const BackendIdSchema = z.enum([
  'ollama',
  'vllm-coder',
  'vllm-planner',
  'vllm-legacy',
  'llamacpp',
  'sglang',
]);
export type BackendId = z.infer<typeof BackendIdSchema>;

export const CreateRunRequestSchema = z.object({
  title: z.string().min(1, 'Task description is required'),
  agentPresetId: z.string().min(1),
  workspaceId: z.string().min(1),
  taskPrompt: z.string().optional(),
  taskComplexity: z.enum(['simple', 'agentic']).default('agentic'),
  contextLength: z.number().int().nonnegative().optional(),
  // Stage 1E — when true, agent pauses before every tool call for HITL
  // approve/reject. UI toggle is gated by the APPROVAL_GATE feature flag.
  requireApproval: z.boolean().optional(),
  // Stage 2.1 — explicit backend pin. Overrides the preset's backendId
  // when set. When omitted, the BFF falls back to the preset (or the
  // default role-based route if the preset has no backendId either).
  backendId: BackendIdSchema.nullish(),
});

export type CreateRunRequest = z.infer<typeof CreateRunRequestSchema>;

// ---------------------------------------------------------------------------
// UI-state schema exported for tests that assert store-shape validity.
// ---------------------------------------------------------------------------
export const RunDetailUIStateSchema = z.object({
  selectedTab: z.enum(['overview', 'events', 'artifacts', 'traces', 'plan', 'diffs', 'browser', 'terminal', 'metrics', 'security', 'notifications']),
  selectedEventId: z.union([z.string(), z.number()]).nullable(),
  diffMode: z.enum(['split', 'unified']),
  inspectorOpen: z.boolean(),
  latestStreamEventId: z.number(),
});
export type RunDetailUIState = z.infer<typeof RunDetailUIStateSchema>;
