import type { SecretRef } from '@/lib/schemas/secret';

// Raw values are NEVER in fixtures — only SecretRef metadata.
export const mockSecrets: SecretRef[] = [
  {
    id: 'secret-gh-token',
    name: 'GITHUB_TOKEN',
    type: 'api_key',
    description: 'Personal access token for GitHub API and git push operations.',
    lastRotatedAt: '2026-07-01T00:00:00.000Z',
    createdAt: '2026-06-01T00:00:00.000Z',
  },
  {
    id: 'secret-openai',
    name: 'OPENAI_API_KEY',
    type: 'api_key',
    description: 'OpenAI API key — used only when cloud fallback is explicitly enabled.',
    lastRotatedAt: null,
    createdAt: '2026-06-01T00:00:00.000Z',
  },
  {
    id: 'secret-ssh',
    name: 'DEPLOY_SSH_KEY',
    type: 'ssh_key',
    description: 'SSH key for deployment target.',
    lastRotatedAt: '2026-07-10T00:00:00.000Z',
    createdAt: '2026-06-15T00:00:00.000Z',
  },
];
