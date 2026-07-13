/**
 * MSW request handlers — complete coverage for all BFF API routes.
 * All fixtures use deterministic seed IDs from src/tests/fixtures/seed.ts.
 *
 * Canonical BFF port: 8081
 */
import { http, HttpResponse } from 'msw';
import { SEED } from '../fixtures/seed';
import { mockRuns } from '../fixtures/runs.fixture';
import { mockWorkspaces } from '../fixtures/workspaces.fixture';
import { mockEvents } from '../fixtures/events.fixture';
import { mockSecrets } from '../fixtures/secrets.fixture';
import { mockPlugins } from '../fixtures/plugins.fixture';
import { mockMCPServers } from '../fixtures/mcp.fixture';
import {
  mockRigpaContext,
  mockContextInjectionResponse,
  mockPackageResponse,
} from '../../features/rigpa-lms/fixtures';

// NEXT_PUBLIC_BFF_URL — canonical BFF port is 8081.
const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export const handlers = [
  // -------------------------------------------------------------------------
  // Runs
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/runs`, () =>
    HttpResponse.json({ data: mockRuns, pageInfo: { total: mockRuns.length, page: 1, pageSize: 20 } })
  ),
  http.post(`${BFF}/api/runs`, () =>
    HttpResponse.json({ data: mockRuns[0] }, { status: 201 })
  ),
  http.get(`${BFF}/api/runs/:runId`, ({ params }) => {
    const run = mockRuns.find((r) => r.id === params.runId) ?? mockRuns[0];
    return HttpResponse.json({ data: run });
  }),
  http.get(`${BFF}/api/runs/:runId/events`, () =>
    HttpResponse.json({ data: mockEvents })
  ),
  http.post(`${BFF}/api/runs/:runId/pause`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.post(`${BFF}/api/runs/:runId/resume`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.post(`${BFF}/api/runs/:runId/stop`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.post(`${BFF}/api/runs/:runId/fork`, ({ params }) =>
    HttpResponse.json({ data: { ...mockRuns[0], id: `run_fork_${params.runId}`, title: `Fork of ${mockRuns[0].title}` } }, { status: 201 })
  ),
  http.post(`${BFF}/api/runs/:runId/approve`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.post(`${BFF}/api/runs/:runId/reject`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.get(`${BFF}/api/runs/compare`, () =>
    HttpResponse.json({
      data: {
        base: mockRuns[0],
        fork: mockRuns[1] ?? mockRuns[0],
        files: [],
        stats: { filesChanged: 0, additions: 0, deletions: 0 },
      },
    })
  ),
  http.get(`${BFF}/api/runs/:runId/traces`, () =>
    HttpResponse.json({
      data: [
        { id: SEED.traces.t1, runId: SEED.runs.r1, spanType: 'LLM', name: 'devstral completion', durationMs: 1240, status: 'ok', parentId: null, startedAt: '2026-07-13T03:45:01Z' },
        { id: SEED.traces.t2, runId: SEED.runs.r1, spanType: 'Tool', name: 'file_editor write', durationMs: 88, status: 'ok', parentId: SEED.traces.t1, startedAt: '2026-07-13T03:45:02Z' },
      ],
    })
  ),

  // -------------------------------------------------------------------------
  // Workspaces
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/workspaces`, () =>
    HttpResponse.json({ data: mockWorkspaces })
  ),
  http.get(`${BFF}/api/workspaces/:id`, ({ params }) => {
    const ws = mockWorkspaces.find((w) => w.id === params.id) ?? mockWorkspaces[0];
    return HttpResponse.json({ data: ws });
  }),
  http.post(`${BFF}/api/workspaces/:id/reset`, () =>
    HttpResponse.json({ ok: true })
  ),

  // -------------------------------------------------------------------------
  // Secrets
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/secrets`, () =>
    HttpResponse.json({ data: mockSecrets })
  ),
  http.post(`${BFF}/api/secrets`, () =>
    HttpResponse.json({ data: mockSecrets[0] }, { status: 201 })
  ),
  http.patch(`${BFF}/api/secrets/:id`, () =>
    HttpResponse.json({ data: mockSecrets[0] })
  ),
  http.delete(`${BFF}/api/secrets/:id`, () =>
    new HttpResponse(null, { status: 204 })
  ),

  // -------------------------------------------------------------------------
  // Plugins & MCP
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/plugins`, () =>
    HttpResponse.json({ data: mockPlugins })
  ),
  http.post(`${BFF}/api/plugins/:id/enable`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.post(`${BFF}/api/plugins/:id/disable`, () =>
    HttpResponse.json({ ok: true })
  ),
  http.get(`${BFF}/api/integrations/mcp`, () =>
    HttpResponse.json({ data: mockMCPServers })
  ),

  // -------------------------------------------------------------------------
  // Agent presets
  // Note: BFF mounts at /api/agent-presets (not /api/agents/presets)
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/agent-presets`, () =>
    HttpResponse.json({
      data: [
        { id: SEED.agents.a1, name: 'DevstralAgentic', model: 'devstral-small:24b', description: 'Multi-file agentic workflows' },
        { id: SEED.agents.a2, name: 'Qwen3Fast', model: 'qwen3:14b', description: 'Fast scripting and summaries' },
      ],
    })
  ),

  // -------------------------------------------------------------------------
  // Observability
  // -------------------------------------------------------------------------
  http.get(`${BFF}/api/observability/summary`, () =>
    HttpResponse.json({
      data: {
        totalRuns: 42,
        successRate: 0.88,
        avgDurationMs: 187000,
        avgCostUsd: 0.038,
        totalTokens: 2_840_000,
        errorRate: 0.12,
      },
    })
  ),
  http.get(`${BFF}/api/observability/runs`, () =>
    HttpResponse.json({ data: mockRuns })
  ),
  http.get(`${BFF}/api/observability/errors`, () =>
    HttpResponse.json({ data: [] })
  ),

  // -------------------------------------------------------------------------
  // Rigpa-LMS (Slice 5C)
  // -------------------------------------------------------------------------
  http.post(`${BFF}/api/lms/context`, () =>
    HttpResponse.json(mockContextInjectionResponse, { status: 201 })
  ),
  http.get(`${BFF}/api/lms/context/:sessionId`, ({ params }) => {
    if (params.sessionId === SEED.lms.session1) {
      return HttpResponse.json(mockRigpaContext);
    }
    return new HttpResponse(null, { status: 404 });
  }),
  http.post(`${BFF}/api/lms/package`, () =>
    HttpResponse.json(mockPackageResponse)
  ),
];
