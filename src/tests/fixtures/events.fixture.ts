import type { ToolEvent } from '@/lib/schemas/event';

export const mockEvents: ToolEvent[] = [
  {
    id: 'evt-001',
    runId: 'run-001',
    type: 'think',
    timestamp: new Date(Date.now() - 60000).toISOString(),
    summary: 'Analyzing auth module structure and Pydantic v1 patterns...',
    source: 'agent',
  },
  {
    id: 'evt-002',
    runId: 'run-001',
    type: 'plan',
    timestamp: new Date(Date.now() - 50000).toISOString(),
    summary: 'Plan: 1) Update models.py validators  2) Update route handlers  3) Run type checks',
    source: 'agent',
  },
  {
    id: 'evt-003',
    runId: 'run-001',
    type: 'edit_file',
    timestamp: new Date(Date.now() - 40000).toISOString(),
    summary: 'Editing bff/models/user.py — replacing @validator with @field_validator',
    source: 'agent',
  },
  {
    id: 'evt-004',
    runId: 'run-001',
    type: 'run_command',
    timestamp: new Date(Date.now() - 30000).toISOString(),
    summary: 'Running: python -m mypy bff/models/ --strict',
    source: 'agent',
  },
];
