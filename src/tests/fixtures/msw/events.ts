import type { EventListResponse } from '../../../lib/schemas/event';

const ts = (offsetMs = 0) => new Date(Date.now() - offsetMs).toISOString();

export const eventsFixture: EventListResponse = {
  latestEventId: 47,
  total: 47,
  events: [
    {
      id: 1,
      eventId: 1,
      type: 'run_started',
      timestamp: ts(12 * 60 * 1000),
      runId: 'run-001',
      summary: 'Run started with Devstral Small 24B',
      payload: { model: 'devstral-small:24b', workspaceType: 'docker' },
    },
    {
      id: 12,
      eventId: 12,
      type: 'plan_update',
      timestamp: ts(10 * 60 * 1000),
      runId: 'run-001',
      summary: 'Plan decomposed into 5 steps',
      payload: { steps: 5, rootGoal: 'Refactor auth middleware' },
    },
    {
      id: 23,
      eventId: 23,
      type: 'file_change',
      timestamp: ts(8 * 60 * 1000),
      runId: 'run-001',
      summary: 'Modified bff/routers/auth.py (+12 -4)',
      payload: { path: 'bff/routers/auth.py', additions: 12, deletions: 4, changeType: 'modified' },
    },
    {
      id: 38,
      eventId: 38,
      type: 'command_end',
      timestamp: ts(5 * 60 * 1000),
      runId: 'run-001',
      summary: 'pytest bff/tests/ — 14 passed, 0 failed',
      payload: { command: 'pytest bff/tests/', exitCode: 0, durationMs: 4200 },
    },
    {
      id: 47,
      eventId: 47,
      type: 'action',
      timestamp: ts(30 * 1000),
      runId: 'run-001',
      summary: 'Editing bff/services/loop_guard.py',
      payload: { tool: 'edit_file', path: 'bff/services/loop_guard.py' },
    },
  ],
};
