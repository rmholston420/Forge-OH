/**
 * src/tests/unit/domain-RestartFromHereButton.test.tsx
 *
 * Stage 6.4c (ADR-026) tests for the restart-from-here confirmation
 * button.  Symmetric to domain-ForkFromHereButton.test.tsx: guards the
 * click-through path, the exact useRestartRun variables (wire-key
 * regression), the feature-flag gate, error surfacing, pending state,
 * and the post-success router.push to the new run's detail page.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RestartFromHereButton } from '@/components/domain/RestartFromHereButton';

// --- mocks ------------------------------------------------------------------

const pushMock = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

const mutateMock = vi.fn();
let mockPending = false;
let mockError: Error | null = null;
const resetMock = vi.fn();

vi.mock('@/features/runs/hooks', () => ({
  useRestartRun: () => ({
    mutate: mutateMock,
    isPending: mockPending,
    error: mockError,
    reset: resetMock,
  }),
}));

// --- helpers ----------------------------------------------------------------

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const originalEnv = { ...process.env };

beforeEach(() => {
  // Stage 6.4c: feature flag defaults ON (parity with fork-from-here).
  process.env = { ...originalEnv, NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED: 'true' };
  pushMock.mockReset();
  mutateMock.mockReset();
  resetMock.mockReset();
  mockPending = false;
  mockError = null;
});

// --- tests ------------------------------------------------------------------

describe('RestartFromHereButton', () => {
  it('renders null when feature flag is disabled', () => {
    process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED = 'false';
    const { container } = render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the trigger button', () => {
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    const btn = screen.getByTestId('restart-from-here-button');
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toMatch(/restart from here/i);
  });

  it('does not open the modal until clicked', () => {
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('clicking the trigger opens the confirmation modal', async () => {
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('includes the optional eventLabel in the dialog body', async () => {
    render(
      <RestartFromHereButton
        runId="src-1"
        eventId="ev-42"
        eventLabel="prompt: refactor auth"
      />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    expect(
      screen.getByText(/prompt: refactor auth/i),
    ).toBeInTheDocument();
  });

  it('dialog body warns that files on disk are reset (ADR-026 promise)', async () => {
    // This is the copy-guard against the ADR-026 §Storage silent-drift
    // failure mode: if the semantics ever regress to "conversation only"
    // (which is what fork does) the copy must NOT keep saying we reset
    // files.  Test fails LOUDLY if the copy loses the resets-files line.
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    expect(
      screen.getByText(/resets files on disk/i),
    ).toBeInTheDocument();
  });

  it('confirm calls useRestartRun with the EXACT { runId, fromEventId } shape', async () => {
    // Wire-key regression: the hook variable name MUST be fromEventId
    // (camelCase at this layer — api.ts maps it to from_event_id on the
    // wire).  If this drifts, the BFF endpoint returns 422 (RestartRunRequest
    // requires from_event_id) or worse, the anchor-not-found path.
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    await userEvent.click(screen.getByTestId('restart-from-here-confirm'));

    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [vars] = mutateMock.mock.calls[0];
    expect(vars).toEqual({ runId: 'src-1', fromEventId: 'ev-42' });
  });

  it('on successful restart, navigates to the new run', async () => {
    mutateMock.mockImplementation((_vars, opts) => {
      opts?.onSuccess?.({
        ok: true,
        restarted_run_id: 'run-new-1',
        source_run_id: 'src-1',
        from_event_id: 'ev-42',
        reset_to_sha: 'a'.repeat(40),
        worktree_path: '/tmp/new-wd',
      });
    });
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    await userEvent.click(screen.getByTestId('restart-from-here-confirm'));

    expect(pushMock).toHaveBeenCalledWith('/runs/run-new-1');
  });

  it('cancel button closes the modal without calling mutate', async () => {
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await userEvent.click(screen.getByText(/^cancel$/i));
    expect(mutateMock).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('surfaces mutation error in a banner inside the dialog', async () => {
    mockError = new Error('no_sha_anchor: ledger has no row for ev-42');
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    expect(
      screen.getByText(/no_sha_anchor/i),
    ).toBeInTheDocument();
  });

  it('confirm button is disabled and aria-busy while the mutation is pending', async () => {
    mockPending = true;
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    const confirm = screen.getByTestId('restart-from-here-confirm');
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute('aria-busy', 'true');
    expect(confirm.textContent).toMatch(/restarting/i);
  });

  it('does NOT navigate if success payload has no restarted_run_id', async () => {
    // Defensive: the BFF endpoint always returns restarted_run_id on 200,
    // but the guard exists in the component and should stay covered.
    mutateMock.mockImplementation((_vars, opts) => {
      opts?.onSuccess?.({ ok: true });
    });
    render(
      <RestartFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('restart-from-here-button'));
    await userEvent.click(screen.getByTestId('restart-from-here-confirm'));

    expect(pushMock).not.toHaveBeenCalled();
  });
});
