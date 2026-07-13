import { http, HttpResponse } from 'msw';
import { mockRuns } from '../fixtures/runs.fixture';
import { mockWorkspaces } from '../fixtures/workspaces.fixture';
import { mockEvents } from '../fixtures/events.fixture';
import { mockSecrets } from '../fixtures/secrets.fixture';
import { mockPlugins } from '../fixtures/plugins.fixture';
import { mockMCPServers } from '../fixtures/mcp.fixture';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export const handlers = [
  http.get(`${BFF}/api/runs`, () => HttpResponse.json({ data: mockRuns })),
  http.post(`${BFF}/api/runs`, () => HttpResponse.json({ data: mockRuns[0] }, { status: 201 })),
  http.get(`${BFF}/api/runs/:runId`, ({ params }) => {
    const run = mockRuns.find((r) => r.id === params.runId) ?? mockRuns[0];
    return HttpResponse.json({ data: run });
  }),
  http.get(`${BFF}/api/runs/:runId/events`, () => HttpResponse.json({ data: mockEvents })),
  http.get(`${BFF}/api/workspaces`, () => HttpResponse.json({ data: mockWorkspaces })),
  http.get(`${BFF}/api/secrets`, () => HttpResponse.json({ data: mockSecrets })),
  http.get(`${BFF}/api/plugins`, () => HttpResponse.json({ data: mockPlugins })),
  http.get(`${BFF}/api/integrations/mcp`, () => HttpResponse.json({ data: mockMCPServers })),
  http.get(`${BFF}/api/agents/presets`, () => HttpResponse.json({ data: [
    { id: 'preset-01', name: 'DevstralAgentic', model: 'devstral-small:24b' },
    { id: 'preset-02', name: 'Qwen3Fast', model: 'qwen3:14b' },
  ]})),
];
