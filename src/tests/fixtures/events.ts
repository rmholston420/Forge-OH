import type { ToolEvent } from '@/lib/schemas/event';

export const mockEvents: ToolEvent[] = [
  {
    id: 'evt-001',
    type: 'message',
    runId: 'run-002',
    timestamp: '2026-07-13T10:00:05.000Z',
    source: 'agent',
    summary: 'Analysing existing /api/runs endpoint to understand pagination needs.',
    payload: {},
  },
  {
    id: 'evt-002',
    type: 'tool_call',
    runId: 'run-002',
    timestamp: '2026-07-13T10:00:12.000Z',
    source: 'agent',
    summary: 'Reading bff/routers/runs.py',
    payload: { tool: 'read_file', path: 'bff/routers/runs.py' },
  },
  {
    id: 'evt-003',
    type: 'tool_result',
    runId: 'run-002',
    timestamp: '2026-07-13T10:00:13.000Z',
    source: 'tool',
    summary: 'Read 87 lines from bff/routers/runs.py',
    payload: { lineCount: 87 },
  },
  {
    id: 'evt-004',
    type: 'file_edit',
    runId: 'run-002',
    timestamp: '2026-07-13T10:01:02.000Z',
    source: 'agent',
    summary: 'Modified bff/routers/runs.py — added cursor-based pagination',
    payload: { path: 'bff/routers/runs.py', additions: 24, deletions: 3 },
  },
  {
    id: 'evt-005',
    type: 'approval_required',
    runId: 'run-003',
    timestamp: '2026-07-13T09:55:00.000Z',
    source: 'agent',
    summary: 'Requesting approval to run pytest with coverage flag',
    payload: { command: 'pytest bff/services/test_loop_guard.py --cov=bff/services', riskLevel: 'low' },
  },
];
