/**
 * src/tests/unit/RepoGraphPanel.test.tsx
 *
 * Slice D.5 — unit tests for the RepoGraph panel.
 *
 * Uses MSW to stub the six BFF endpoints and React Query to drive the
 * component. Covers:
 *   - disabled state when the feature flag is off
 *   - health badge (reachable=true vs error)
 *   - index → search → select → callers/callees/co_changed flow
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  fireEvent,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { RepoGraphPanel } from '@/components/domain/RepoGraphPanel';

const BFF = 'http://localhost:8081';

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const ORIG_ENV = { ...process.env };

beforeEach(() => {
  process.env.NEXT_PUBLIC_FEATURE_REPOGRAPH = 'true';
});

afterEach(() => {
  process.env = { ...ORIG_ENV };
  vi.restoreAllMocks();
});

describe('RepoGraphPanel — disabled', () => {
  it('renders disabled hint when the flag is off', () => {
    delete process.env.NEXT_PUBLIC_FEATURE_REPOGRAPH;
    renderWithClient(<RepoGraphPanel />);
    expect(screen.getByTestId('repograph-panel-disabled')).toBeInTheDocument();
    // "disabled" appears in both header badge and body hint — both are fine.
    expect(screen.getAllByText(/disabled/i).length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(/NEXT_PUBLIC_FEATURE_REPOGRAPH/),
    ).toBeInTheDocument();
  });
});

describe('RepoGraphPanel — enabled', () => {
  it('shows a green health badge when Neo4j is reachable', async () => {
    server.use(
      http.get(`${BFF}/api/repograph/health`, () =>
        HttpResponse.json({
          enabled: true,
          reachable: true,
          neo4j_version: '5.26.27',
          neo4j_edition: 'enterprise',
          database: 'forgeoh',
          error: null,
        }),
      ),
    );

    renderWithClient(<RepoGraphPanel />);
    await waitFor(() =>
      expect(screen.getByTitle('Neo4j status').textContent).toMatch(
        /5\.26\.27/,
      ),
    );
    expect(screen.getByTitle('Neo4j status').getAttribute('data-ok')).toBe(
      'true',
    );
  });

  it('shows a red badge when Neo4j is unreachable', async () => {
    server.use(
      http.get(`${BFF}/api/repograph/health`, () =>
        HttpResponse.json({
          enabled: true,
          reachable: false,
          neo4j_version: null,
          neo4j_edition: null,
          database: null,
          error: 'Bolt closed',
        }),
      ),
    );

    renderWithClient(<RepoGraphPanel />);
    await waitFor(() =>
      expect(screen.getByTitle('Neo4j status').textContent).toMatch(
        /Bolt closed/,
      ),
    );
    expect(screen.getByTitle('Neo4j status').getAttribute('data-ok')).toBe(
      'false',
    );
  });

  it('indexes a workspace then searches + selects a symbol', async () => {
    server.use(
      http.get(`${BFF}/api/repograph/health`, () =>
        HttpResponse.json({
          enabled: true,
          reachable: true,
          neo4j_version: '5.26.27',
          neo4j_edition: 'enterprise',
          database: 'forgeoh',
          error: null,
        }),
      ),
      http.post(`${BFF}/api/repograph/index`, async () =>
        HttpResponse.json({
          repo_key: 'abc123def456',
          workspace_path: '/home/rmholston/dev/forge-oh',
          stats: { files: 3, symbols: 5, calls: 7, method_edges: 1 },
        }),
      ),
      http.get(`${BFF}/api/repograph/search`, () =>
        HttpResponse.json([
          {
            rel_path: 'bff/main.py',
            name: 'lifespan',
            category: 'function',
            start_line: 46,
            end_line: 57,
            parent: null,
            info: 'async def lifespan(app: FastAPI):',
            pagerank: 0.11,
          },
        ]),
      ),
      http.get(`${BFF}/api/repograph/callers`, () =>
        HttpResponse.json([
          {
            caller_file: 'bff/routers/runs.py',
            callee_file: 'bff/main.py',
            callee: 'lifespan',
            callee_line: 46,
            call_line: 10,
          },
        ]),
      ),
      http.get(`${BFF}/api/repograph/callees`, () =>
        HttpResponse.json([
          {
            callee_file: 'bff/services/event_relay.py',
            callee: 'start_relay',
            category: 'function',
            callee_line: 172,
            call_line: 55,
            pagerank: 0.02,
          },
        ]),
      ),
      http.get(`${BFF}/api/repograph/co_changed`, () =>
        HttpResponse.json({
          target: 'bff/main.py',
          window: 50,
          files: [{ rel_path: 'bff/routers/runs.py', commits: 8 }],
          available: true,
          error: null,
        }),
      ),
    );

    renderWithClient(<RepoGraphPanel />);

    // Wait for the "Index" button to become enabled (needs healthy Neo4j).
    const indexBtn = await screen.findByRole('button', { name: /index/i });
    await waitFor(() => expect(indexBtn).not.toBeDisabled());

    // Fill in a workspace path and index.
    const wsInput = screen.getByLabelText(/workspace path/i);
    fireEvent.change(wsInput, {
      target: { value: '/home/rmholston/dev/forge-oh' },
    });
    fireEvent.click(indexBtn);

    // Stats line appears once the mutation succeeds.
    await waitFor(() =>
      expect(screen.getByText(/files 3/)).toBeInTheDocument(),
    );

    // Search box appears now that repoKey is set.
    const searchInput = screen.getByLabelText(/search symbols/i);
    fireEvent.change(searchInput, { target: { value: 'life' } });

    const lifespanRow = await screen.findByText('lifespan');
    fireEvent.click(lifespanRow);

    // Callers + callees + co_changed columns render.
    await waitFor(() =>
      expect(screen.getByText(/Callers of lifespan/)).toBeInTheDocument(),
    );
    // bff/routers/runs.py appears in both Callers and Co-changed columns.
    const runsMatches = await screen.findAllByText('bff/routers/runs.py');
    expect(runsMatches.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText('start_relay')).toBeInTheDocument();
    expect(await screen.findByText(/8 commits/)).toBeInTheDocument();
  });
});
