/**
 * src/tests/unit/domain-ForkRunModal.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ForkRunModal } from '@/components/domain/ForkRunModal';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush }) }));

const originalEnv = process.env;

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const base = { runId: 'run-1', runTitle: 'My Run', open: true, onClose: vi.fn() };

beforeEach(() => {
  process.env = { ...originalEnv, NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED: 'true' };
  vi.clearAllMocks();
});

describe('ForkRunModal', () => {
  it('renders null when feature flag is disabled', () => {
    process.env.NEXT_PUBLIC_FEATURE_RUN_COMPARE_ENABLED = 'false';
    const { container } = render(<ForkRunModal {...base} />, { wrapper });
    expect(container.firstChild).toBeNull();
  });

  it('renders null when open=false', () => {
    const { container } = render(<ForkRunModal {...base} open={false} />, { wrapper });
    expect(container.firstChild).toBeNull();
  });

  it('renders modal title', () => {
    render(<ForkRunModal {...base} />, { wrapper });
    expect(screen.getByText(/fork run/i)).toBeInTheDocument();
  });

  it('renders Fork run button', () => {
    render(<ForkRunModal {...base} />, { wrapper });
    expect(screen.getByRole('button', { name: /fork run/i })).toBeInTheDocument();
  });

  it('Cancel button calls onClose', async () => {
    const onClose = vi.fn();
    render(<ForkRunModal {...base} onClose={onClose} />, { wrapper });
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('checkbox for compare-after is checked by default', () => {
    render(<ForkRunModal {...base} />, { wrapper });
    const checkbox = screen.getByRole('checkbox');
    expect((checkbox as HTMLInputElement).checked).toBe(true);
  });

  it('checkbox can be toggled', async () => {
    render(<ForkRunModal {...base} />, { wrapper });
    const checkbox = screen.getByRole('checkbox');
    await userEvent.click(checkbox);
    expect((checkbox as HTMLInputElement).checked).toBe(false);
  });
});
