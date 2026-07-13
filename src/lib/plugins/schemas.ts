import { z } from 'zod';

export const PluginEventType = {
  RUN_STARTED:       'run_started',
  RUN_COMPLETED:     'run_completed',
  RUN_FAILED:        'run_failed',
  APPROVAL_REQUIRED: 'approval_required',
  PLAN_UPDATED:      'plan_updated',
  ARTIFACT_READY:    'artifact_ready',
  WORKSPACE_READY:   'workspace_ready',
  AGENT_MESSAGE:     'agent_message',
} as const;
export type PluginEventType = typeof PluginEventType[keyof typeof PluginEventType];

export const PluginAuthType = z.enum(['none', 'bearer', 'api_key']);

export const PluginManifestSchema = z.object({
  id:           z.string().uuid(),
  name:         z.string().min(1),
  version:      z.string().regex(/^\d+\.\d+\.\d+$/),
  description:  z.string().optional(),
  baseUrl:      z.string().url(),
  authType:     PluginAuthType.default('none'),
  secret:       z.string().optional(),   // HMAC secret for webhook verification
  capabilities: z.array(z.nativeEnum(PluginEventType)).default([]),
});
export type PluginManifest = z.infer<typeof PluginManifestSchema>;

export const PluginEventSchema = z.object({
  id:          z.string().uuid(),
  source:      z.string(),              // emitting app id
  type:        z.nativeEnum(PluginEventType),
  payload:     z.record(z.unknown()),
  runId:       z.string().optional(),
  workspaceId: z.string().optional(),
  timestamp:   z.string().datetime(),
  signature:   z.string().optional(),  // HMAC-SHA256 of JSON payload
});
export type PluginEvent = z.infer<typeof PluginEventSchema>;

export const InboundCommandSchema = z.discriminatedUnion('command', [
  z.object({ command: z.literal('approve_run'), runId: z.string() }),
  z.object({ command: z.literal('stop_run'),    runId: z.string() }),
  z.object({ command: z.literal('create_run'),  agentPreset: z.string(), workspaceId: z.string() }),
]);
export type InboundCommand = z.infer<typeof InboundCommandSchema>;
