/**
 * src/tests/unit/domain-ForkFromHereButton.test.tsx
 *
 * Stage 6.4 tests for the fork-from-here confirmation button.  These
 * tests defend the click-through path and the exact useForkRun variables
 * (regression against the silent-full-fork trap where the wrong key
 * makes agent-server produce a full fork with forked_from_event_id=null).
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ForkFromHereButton } from '@/components/domain/ForkFromHereButton';

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
  useForkRun: () => ({
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
  // Stage 6.4 close-out: feature flag defaults ON. Individual tests can
  // flip it off to assert the gate.
  process.env = { ...originalEnv, NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED: 'true' };
  pushMock.mockReset();
  mutateMock.mockReset();
  resetMock.mockReset();
  mockPending = false;
  mockError = null;
});

// --- tests ------------------------------------------------------------------

describe('ForkFromHereButton', () => {
  it('renders null when feature flag is disabled', () => {
    process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED = 'false';
    const { container } = render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders the trigger button', () => {
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    const btn = screen.getByTestId('fork-from-here-button');
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toMatch(/fork from here/i);
  });

  it('does not open the modal until clicked', () => {
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('clicking the trigger opens the confirmation modal', async () => {
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('includes the optional eventLabel in the dialog body', async () => {
    render(
      <ForkFromHereButton
        runId="src-1"
        eventId="ev-42"
        eventLabel="prompt: refactor auth"
      />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    expect(
      screen.getByText(/prompt: refactor auth/i),
    ).toBeInTheDocument();
  });

  it('confirm calls useForkRun with the EXACT { runId, fromEventId } shape', async () => {
    // This is the critical regression against silent-full-fork.  The hook
    // variable name MUST be fromEventId (camelCase at this layer — the
    // api.ts layer maps it to from_event_id on the wire).
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    await userEvent.click(screen.getByTestId('fork-from-here-confirm'));

    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [vars] = mutateMock.mock.calls[0];
    expect(vars).toEqual({ runId: 'src-1', fromEventId: 'ev-42' });
  });

  it('on successful fork, navigates to the new run', async () => {
    mutateMock.mockImplementation((_vars, opts) => {
      opts?.onSuccess?.({
        ok: true,
        run_id: 'src-1',
        forked_id: 'fork-D',
        from_event_id: 'ev-42',
      });
    });
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    await userEvent.click(screen.getByTestId('fork-from-here-confirm'));

    expect(pushMock).toHaveBeenCalledWith('/runs/fork-D');
  });

  it('cancel button closes the modal without calling mutate', async () => {
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await userEvent.click(screen.getByText(/^cancel$/i));
    expect(mutateMock).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('surfaces mutation error in a banner inside the dialog', async () => {
    mockError = new Error('unknown from_event_id');
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    expect(
      screen.getByText(/unknown from_event_id/i),
    ).toBeInTheDocument();
  });

  it('confirm button is disabled while the mutation is pending', async () => {
    mockPending = true;
    render(
      <ForkFromHereButton runId="src-1" eventId="ev-42" />,
      { wrapper },
    );
    await userEvent.click(screen.getByTestId('fork-from-here-button'));
    const confirm = screen.getByTestId('fork-from-here-confirm');
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute('aria-busy', 'true');
  });
});
