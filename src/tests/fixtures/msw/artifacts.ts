import type { ArtifactListResponse } from '../../../lib/schemas/artifact';

const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const artifactsFixture: ArtifactListResponse = {
  total: 3,
  artifacts: [
    {
      id: 'artifact-001',
      runId: 'run-001',
      type: 'file_change',
      name: 'bff/routers/auth.py',
      path: 'bff/routers/auth.py',
      mimeType: 'text/x-python',
      sizeBytes: 2840,
      createdAt: ago(8 * 60 * 1000),
      isBinary: false,
    },
    {
      id: 'artifact-002',
      runId: 'run-001',
      type: 'file_change',
      name: 'bff/services/loop_guard.py',
      path: 'bff/services/loop_guard.py',
      mimeType: 'text/x-python',
      sizeBytes: 1620,
      createdAt: ago(30 * 1000),
      isBinary: false,
    },
    {
      id: 'artifact-003',
      runId: 'run-001',
      type: 'report',
      name: 'pytest-results.json',
      path: 'pytest-results.json',
      mimeType: 'application/json',
      sizeBytes: 4100,
      createdAt: ago(5 * 60 * 1000),
      isBinary: false,
    },
  ],
};
