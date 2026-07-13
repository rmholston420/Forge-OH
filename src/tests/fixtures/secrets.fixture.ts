import type { SecretRef } from '@/lib/schemas/secret';

export const mockSecrets: SecretRef[] = [
  {
    id: 'sec-001',
    name: 'OPENAI_API_KEY',
    maskedValue: 'sk-••••••••••••••••••••••••••••••••••••',
    scope: 'global',
    createdAt: '2026-07-01T00:00:00Z',
    updatedAt: '2026-07-01T00:00:00Z',
  },
  {
    id: 'sec-002',
    name: 'GITHUB_TOKEN',
    maskedValue: 'ghp_••••••••••••••••••••••••••••••••••',
    scope: 'workspace',
    scopeId: 'ws-local-001',
    createdAt: '2026-07-02T00:00:00Z',
    updatedAt: '2026-07-02T00:00:00Z',
  },
];
