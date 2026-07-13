import type { SecretRef } from '@/lib/schemas/secret';

/**
 * Mock secrets — shape aligned with SecretRefSchema.
 * Uses `valueStatus` enum ('masked' | 'unset'); never includes raw secret values.
 */
export const mockSecrets: SecretRef[] = [
  {
    id: 'sec-001',
    name: 'OPENAI_API_KEY',
    description: 'OpenAI API key for model calls',
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: '2026-07-01T00:00:00Z',
    valueStatus: 'masked',
    usedByWorkspaces: ['ws-local-001'],
    usedByRuns: 3,
  },
  {
    id: 'sec-002',
    name: 'GITHUB_TOKEN',
    description: 'GitHub personal access token for repo operations',
    createdAt: '2026-07-02T00:00:00Z',
    updatedAt: '2026-07-02T00:00:00Z',
    valueStatus: 'masked',
    usedByWorkspaces: ['ws-local-001', 'ws-docker-001'],
    usedByRuns: 7,
  },
  {
    id: 'sec-003',
    name: 'SLACK_WEBHOOK_URL',
    description: 'Slack webhook for run notifications',
    createdAt: '2026-07-03T00:00:00Z',
    updatedAt: '2026-07-03T00:00:00Z',
    valueStatus: 'unset',
  },
];
