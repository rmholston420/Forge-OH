import { z } from 'zod';

export const PluginEventType = {
  RUN_STARTED: 'run_started',
  RUN_COMPLETED: 'run_completed',
  RUN_FAILED: 'run_failed',
  APPROVAL_REQUIRED: 'approval_required',
  PLAN_UPDATED: 'plan_updated',
  ARTIFACT_READY: 'artifact_ready',
  WORKSPACE_READY: 'workspace_ready',
  AGENT_MESSAGE: 'agent_message',
} as const;
export type PluginEventType = typeof PluginEventType[keyof typeof PluginEventType];

export const PluginAuthType = z.enum(['none', 'bearer', 'api_key']);

const permissiveUuid = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

export const PluginManifestSchema = z.object({
  id: z.string().regex(permissiveUuid, 'Invalid UUID'),
  name: z.string().min(1),
  version: z.string().regex(/^\d+\.\d+\.\d+$/),
  description: z.string().optional(),
  baseUrl: z.string().url(),
  authType: PluginAuthType.default('none'),
  secret: z.string().optional(),
  capabilities: z.array(z.nativeEnum(PluginEventType)).default([]),
});
export type PluginManifest = z.infer<typeof PluginManifestSchema>;

export const PluginEventSchema = z.object({
  id: z.string().regex(permissiveUuid, 'Invalid UUID'),
  source: z.string(),
  type: z.nativeEnum(PluginEventType),
  payload: z.record(z.string(), z.unknown()),
  runId: z.string().optional(),
  workspaceId: z.string().optional(),
  timestamp: z.string().datetime({ offset: true }),
  signature: z.string().optional(),
});
export type PluginEvent = z.infer<typeof PluginEventSchema>;

export const InboundCommandSchema = z.discriminatedUnion('command', [
  z.object({ command: z.literal('approve_run'), runId: z.string() }),
  z.object({ command: z.literal('stop_run'), runId: z.string() }),
  z.object({ command: z.literal('create_run'), agentPreset: z.string(), workspaceId: z.string() }),
]);
export type InboundCommand = z.infer<typeof InboundCommandSchema>;
