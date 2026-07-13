import { http, HttpResponse } from 'msw';
import { runsFixture, runDetailFixture } from './runs';
import { eventsFixture } from './events';
import { workspacesFixture } from './workspaces';
import { pluginsFixture } from './plugins';
import { mcpServersFixture } from './mcp';
import { secretsFixture } from './secrets';
import { artifactsFixture } from './artifacts';
import { agentPresetsFixture } from './agent-presets';

const API = '/api';

export const handlers = [
  // Runs
  http.get(`${API}/runs`, () => HttpResponse.json(runsFixture)),
  http.post(`${API}/runs`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    const newRun = {
      id: `run-${Date.now()}`,
      title: String(body.title ?? body.taskPrompt ?? 'New Run').slice(0, 60),
      status: 'queued',
      agentPresetName: 'Devstral Agentic',
      workspaceId: String(body.workspaceId ?? 'ws-local-1'),
      workspaceType: 'docker',
      activeTool: null,
      updatedAt: new Date().toISOString(),
      createdAt: new Date().toISOString(),
      elapsedMs: null,
      estimatedCostUsd: null,
    };
    return HttpResponse.json(newRun, { status: 201 });
  }),
  http.get(`${API}/runs/:runId`, ({ params }) => {
    const run = { ...runDetailFixture, id: String(params.runId) };
    return HttpResponse.json(run);
  }),
  http.post(`${API}/runs/:runId/pause`, ({ params }) =>
    HttpResponse.json({ id: params.runId, status: 'paused' }),
  ),
  http.post(`${API}/runs/:runId/resume`, ({ params }) =>
    HttpResponse.json({ id: params.runId, status: 'running' }),
  ),
  http.post(`${API}/runs/:runId/stop`, ({ params }) =>
    HttpResponse.json({ id: params.runId, status: 'stopped' }),
  ),

  // Events
  http.get(`${API}/runs/:runId/events`, () => HttpResponse.json(eventsFixture)),

  // Artifacts
  http.get(`${API}/runs/:runId/artifacts`, () => HttpResponse.json(artifactsFixture)),
  http.get(`${API}/runs/:runId/artifacts/files`, () =>
    HttpResponse.json(artifactsFixture),
  ),
  http.get(`${API}/runs/:runId/export/patch`, () =>
    new HttpResponse('--- a/src/example.ts\n+++ b/src/example.ts\n@@ -1,3 +1,3 @@\n-const x = 1;\n+const x = 2;\n', {
      headers: { 'Content-Type': 'text/plain' },
    }),
  ),

  // Workspaces
  http.get(`${API}/workspaces`, () => HttpResponse.json(workspacesFixture)),

  // Plugins
  http.get(`${API}/plugins`, () => HttpResponse.json(pluginsFixture)),
  http.patch(`${API}/plugins/:pluginId`, ({ params }) =>
    HttpResponse.json({ id: params.pluginId, status: 'enabled' }),
  ),

  // MCP
  http.get(`${API}/mcp`, () => HttpResponse.json(mcpServersFixture)),

  // Secrets
  http.get(`${API}/secrets`, () => HttpResponse.json(secretsFixture)),
  http.post(`${API}/secrets`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json(
      { id: `secret-${Date.now()}`, name: body.name, valueStatus: 'masked', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
      { status: 201 },
    );
  }),
  http.delete(`${API}/secrets/:secretId`, () =>
    new HttpResponse(null, { status: 204 }),
  ),

  // Agent presets
  http.get(`${API}/agents/presets`, () => HttpResponse.json(agentPresetsFixture)),

  // Observability
  http.get(`${API}/observability`, () =>
    HttpResponse.json({ summary: { totalRuns: 12, successRate: 0.83, avgDurationMs: 45000, totalCostUsd: 1.24 } }),
  ),
];
