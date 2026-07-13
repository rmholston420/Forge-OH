/**
 * src/tests/unit/domain-SecretUpsertModal.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SecretUpsertModal } from '@/components/domain/SecretUpsertModal';

vi.mock('@/features/secrets/hooks', () => ({
  useUpsertSecret: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('SecretUpsertModal', () => {
  it('renders null when open=false', () => {
    const { container } = render(<SecretUpsertModal open={false} onClose={vi.fn()} />, { wrapper });
    expect(container.firstChild).toBeNull();
  });

  it('has role=dialog when open', () => {
    render(<SecretUpsertModal open onClose={vi.fn()} />, { wrapper });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('renders Name field', () => {
    render(<SecretUpsertModal open onClose={vi.fn()} />, { wrapper });
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it('renders Value field as password', () => {
    render(<SecretUpsertModal open onClose={vi.fn()} />, { wrapper });
    expect(document.querySelector('input[type="password"]')).not.toBeNull();
  });

  it('renders Scope selector with three options', () => {
    render(<SecretUpsertModal open onClose={vi.fn()} />, { wrapper });
    const select = screen.getByLabelText(/scope/i);
    expect(select.querySelectorAll('option')).toHaveLength(3);
  });

  it('Escape key calls onClose', () => {
    const onClose = vi.fn();
    render(<SecretUpsertModal open onClose={onClose} />, { wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('Close button calls onClose', async () => {
    const onClose = vi.fn();
    render(<SecretUpsertModal open onClose={onClose} />, { wrapper });
    await userEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('inner modal click does NOT call onClose (stopPropagation)', async () => {
    const onClose = vi.fn();
    render(<SecretUpsertModal open onClose={onClose} />, { wrapper });
    await userEvent.click(screen.getByLabelText(/name/i));
    expect(onClose).not.toHaveBeenCalled();
  });
});
