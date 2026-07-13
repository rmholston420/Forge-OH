import type { SecretListResponse } from '../../../lib/schemas/secret';

const now = new Date().toISOString();
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const secretsFixture: SecretListResponse = {
  total: 3,
  secrets: [
    {
      id: 'secret-001',
      name: 'GITHUB_TOKEN',
      description: 'GitHub personal access token for repo operations',
      createdAt: ago(7 * 24 * 60 * 60 * 1000),
      updatedAt: ago(1 * 24 * 60 * 60 * 1000),
      valueStatus: 'masked',
      usedByWorkspaces: ['ws-docker-1'],
      usedByRuns: 8,
    },
    {
      id: 'secret-002',
      name: 'ANTHROPIC_API_KEY',
      description: 'Cloud fallback key — only used when vLLM is unavailable',
      createdAt: ago(14 * 24 * 60 * 60 * 1000),
      updatedAt: ago(14 * 24 * 60 * 60 * 1000),
      valueStatus: 'masked',
      usedByWorkspaces: [],
      usedByRuns: 1,
    },
    {
      id: 'secret-003',
      name: 'JIRA_API_TOKEN',
      description: 'Jira connector auth token',
      createdAt: ago(10 * 24 * 60 * 60 * 1000),
      updatedAt: ago(10 * 24 * 60 * 60 * 1000),
      valueStatus: 'unset',
      usedByWorkspaces: [],
      usedByRuns: 0,
    },
  ],
};
