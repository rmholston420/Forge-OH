import type { WorkspaceListResponse } from '../../../lib/schemas/workspace';

/**
 * Stage 6: only `local` workspaces are supported. Fixtures reflect the
 * minimal agent-server WorkspaceItem shape (id, name, path, parentPath?)
 * plus safe defaults for optional UI fields.
 */
const now = new Date().toISOString();
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const workspacesFixture: WorkspaceListResponse = {
  total: 2,
  workspaces: [
    {
      id: 'ws-local-1',
      name: 'default',
      type: 'local',
      path: '/home/user/dev/forge-oh/workspaces/default',
      parentPath: '/home/user/dev/forge-oh/workspaces',
      description: 'Primary local workspace',
      health: 'healthy',
      status: 'idle',
      createdAt: ago(7 * 24 * 60 * 60 * 1000),
      updatedAt: now,
      runCount: 0,
      diskUsageMb: 0,
      diskLimitMb: 2048,
      envVars: [],
      agentPresetId: null,
    },
    {
      id: 'ws-local-2',
      name: 'sandbox',
      type: 'local',
      path: '/tmp/forge-sandbox',
      parentPath: null,
      description: 'Sandbox for destructive/risky operations',
      health: 'healthy',
      status: 'idle',
      createdAt: ago(3 * 24 * 60 * 60 * 1000),
      updatedAt: ago(2 * 60 * 60 * 1000),
      runCount: 0,
      diskUsageMb: 0,
      diskLimitMb: 2048,
      envVars: [],
      agentPresetId: null,
    },
  ],
};
