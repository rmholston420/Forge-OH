/**
 * src/tests/unit/TrajectoryMemoryPanel.test.tsx
 *
 * Slice F.7 — unit tests for the trajectory memory case-retrieval panel.
 *
 * Uses MSW to stub POST /api/trajectories/search and React Query to
 * drive the component. Covers:
 *   - disabled state when FEATURE_TRAJECTORY_MEMORY is off
 *   - idle state when taskDescription is empty/undefined
 *   - error surface when the BFF returns a non-2xx
 *   - empty state when hits[] is []
 *   - populated state renders one row per hit with the right badges
 *     and scores
 *   - status pill maps success / failed / verified_failure / other
 */
import React from 'react';
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { TrajectoryMemoryPanel } from '@/components/domain/TrajectoryMemoryPanel';

const BFF = 'http://localhost:8081';

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function makeRecord(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    trajectory_id: 'traj_r1',
    run_id: 'r1',
    session_id: 's1',
    task_description: 'Fix flaky auth test',
    plan: '',
    diffs: [
      { path: 'a.py', lines_added: 3, lines_removed: 1, summary: '' },
    ],
    verify_iterations: [],
    final_status: 'success',
    symptom: 'AssertionError: expected 200 got 401',
    repograph_repo_key: 'rk1',
    repograph_symbols: ['auth.login'],
    embedding: null,
    embedding_model: 'bge-code-v1',
    created_at: '2026-08-03T09:00:00Z',
    ...overrides,
  };
}

const ORIG_ENV = { ...process.env };

beforeEach(() => {
  process.env.NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY = 'true';
});

afterEach(() => {
  process.env = { ...ORIG_ENV };
  vi.restoreAllMocks();
});

describe('TrajectoryMemoryPanel — disabled', () => {
  it('renders the disabled hint when the flag is off', () => {
    delete process.env.NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY;
    renderWithClient(
      <TrajectoryMemoryPanel taskDescription="anything" />,
    );
    expect(
      screen.getByTestId('trajectory-memory-panel-disabled'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY/),
    ).toBeInTheDocument();
  });
});

describe('TrajectoryMemoryPanel — enabled', () => {
  it('shows the idle hint when taskDescription is empty', () => {
    renderWithClient(<TrajectoryMemoryPanel taskDescription="" />);
    expect(
      screen.getByTestId('trajectory-memory-idle'),
    ).toBeInTheDocument();
  });

  it('shows the idle hint when taskDescription is undefined', () => {
    renderWithClient(<TrajectoryMemoryPanel taskDescription={undefined} />);
    expect(
      screen.getByTestId('trajectory-memory-idle'),
    ).toBeInTheDocument();
  });

  it('renders empty state when hits[] is empty', async () => {
    server.use(
      http.post(`${BFF}/api/trajectories/search`, () =>
        HttpResponse.json({
          query: 'Fix flaky auth test',
          k: 3,
          hits: [],
        }),
      ),
    );

    renderWithClient(
      <TrajectoryMemoryPanel taskDescription="Fix flaky auth test" />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId('trajectory-memory-empty'),
      ).toBeInTheDocument(),
    );
  });

  it('renders one row per hit with score, badges, and meta', async () => {
    server.use(
      http.post(`${BFF}/api/trajectories/search`, () =>
        HttpResponse.json({
          query: 'Fix flaky auth test',
          k: 3,
          hits: [
            {
              record: makeRecord({
                trajectory_id: 'traj_A',
                run_id: 'rA',
                task_description: 'Prior — auth 401',
                final_status: 'success',
              }),
              score: 0.8123,
              semantic_score: 0.9,
              symbol_overlap: 0.4,
            },
            {
              record: makeRecord({
                trajectory_id: 'traj_B',
                run_id: 'rB',
                task_description: 'Prior — race in login',
                final_status: 'failed',
                symptom: 'timeout waiting for token',
                repograph_repo_key: 'rk2',
                verify_iterations: [],
                diffs: [],
              }),
              score: 0.55,
              semantic_score: 0.6,
              symbol_overlap: 0.2,
            },
          ],
        }),
      ),
    );

    renderWithClient(
      <TrajectoryMemoryPanel taskDescription="Fix flaky auth test" />,
    );

    const hits = await waitFor(() =>
      screen.getAllByTestId('trajectory-memory-hit'),
    );
    expect(hits.length).toBe(2);

    expect(screen.getByText('Prior — auth 401')).toBeInTheDocument();
    expect(screen.getByText('Prior — race in login')).toBeInTheDocument();

    // Scores rounded to 2dp
    expect(screen.getByText('score 0.81')).toBeInTheDocument();
    expect(screen.getByText('score 0.55')).toBeInTheDocument();

    // Status pills
    const statuses = screen.getAllByTestId('trajectory-status');
    expect(statuses[0].textContent).toMatch(/success/);
    expect(statuses[1].textContent).toMatch(/failed/);
  });

  it('renders the error surface when the BFF returns 500', async () => {
    server.use(
      http.post(`${BFF}/api/trajectories/search`, () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    renderWithClient(
      <TrajectoryMemoryPanel taskDescription="Something to search" />,
    );
    await waitFor(() =>
      expect(
        screen.getByTestId('trajectory-memory-error'),
      ).toBeInTheDocument(),
    );
  });

  it('renders verified_failure with a friendly label', async () => {
    server.use(
      http.post(`${BFF}/api/trajectories/search`, () =>
        HttpResponse.json({
          query: 'x',
          k: 3,
          hits: [
            {
              record: makeRecord({
                trajectory_id: 'traj_V',
                run_id: 'rV',
                final_status: 'verified_failure',
              }),
              score: 0.5,
              semantic_score: 0.5,
              symbol_overlap: 0.5,
            },
          ],
        }),
      ),
    );

    renderWithClient(<TrajectoryMemoryPanel taskDescription="x" />);
    const pill = await waitFor(() =>
      screen.getByTestId('trajectory-status'),
    );
    expect(pill.textContent).toMatch(/verified failure/);
  });
});
