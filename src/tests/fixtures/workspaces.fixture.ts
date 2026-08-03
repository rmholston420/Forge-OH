import type { Workspace } from '@/lib/schemas/workspace';

/**
 * Stage 6: only `local` workspaces are supported. Fixtures reflect the
 * minimal agent-server WorkspaceItem shape.
 */
export const mockWorkspaces: Workspace[] = [
  {
    id: 'ws-local-001',
    name: 'Local Dev',
    type: 'local',
    path: '/home/user/dev/forge-oh/workspaces/local-dev',
    parentPath: '/home/user/dev/forge-oh/workspaces',
    health: 'healthy',
    status: 'idle',
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: new Date().toISOString(),
    runCount: 0,
    diskUsageMb: 0,
    diskLimitMb: 2048,
    envVars: [],
  },
  {
    id: 'ws-local-002',
    name: 'Sandbox',
    type: 'local',
    path: '/tmp/forge-sandbox',
    parentPath: null,
    health: 'healthy',
    status: 'idle',
    createdAt: '2026-07-05T00:00:00Z',
    updatedAt: new Date().toISOString(),
    runCount: 0,
    diskUsageMb: 0,
    diskLimitMb: 2048,
    envVars: [],
  },
];
