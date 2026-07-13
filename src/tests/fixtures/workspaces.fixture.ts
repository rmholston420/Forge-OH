import type { Workspace } from '@/lib/schemas/workspace';

export const mockWorkspaces: Workspace[] = [
  {
    id: 'ws-local-001',
    name: 'Local Dev',
    type: 'local',
    health: 'healthy',
    agentServerUrl: 'http://localhost:3000',
    isolationMode: 'process',
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: new Date().toISOString(),
  },
  {
    id: 'ws-docker-001',
    name: 'Docker Sandbox',
    type: 'docker',
    health: 'healthy',
    agentServerUrl: 'http://localhost:3001',
    isolationMode: 'container',
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: new Date().toISOString(),
  },
  {
    id: 'ws-remote-001',
    name: 'Remote API',
    type: 'remote_api',
    health: 'warning',
    agentServerUrl: 'https://api.example.com/openhands',
    isolationMode: 'managed',
    createdAt: '2026-07-05T00:00:00Z',
    updatedAt: new Date().toISOString(),
  },
];
