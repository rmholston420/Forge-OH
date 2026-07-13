import type { WorkspaceListResponse } from '../../../lib/schemas/workspace';

const now = new Date().toISOString();
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const workspacesFixture: WorkspaceListResponse = {
  total: 3,
  workspaces: [
    {
      id: 'ws-docker-1',
      name: 'Primary Docker Workspace',
      type: 'docker',
      health: 'healthy',
      description: 'Main agentic workspace running forge-oh dev container',
      dockerImage: 'ghcr.io/all-hands-ai/openhands:cloud-1.46.0',
      createdAt: ago(7 * 24 * 60 * 60 * 1000),
      updatedAt: now,
      isDefault: true,
    },
    {
      id: 'ws-docker-2',
      name: 'Isolated Test Workspace',
      type: 'docker',
      health: 'degraded',
      description: 'Ephemeral workspace for destructive or risky operations',
      dockerImage: 'ghcr.io/all-hands-ai/openhands:cloud-1.46.0',
      createdAt: ago(3 * 24 * 60 * 60 * 1000),
      updatedAt: ago(2 * 60 * 60 * 1000),
      isDefault: false,
    },
    {
      id: 'ws-local-1',
      name: 'Local Filesystem',
      type: 'local',
      health: 'healthy',
      description: 'Direct access to local filesystem — use with caution',
      localPath: '/home/user/projects',
      createdAt: ago(14 * 24 * 60 * 60 * 1000),
      updatedAt: ago(24 * 60 * 60 * 1000),
      isDefault: false,
    },
  ],
};
