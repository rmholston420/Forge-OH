/**
 * src/tests/unit/workspaces-DeleteConfirmDialog.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DeleteConfirmDialog } from '@/features/workspaces/DeleteConfirmDialog';

const mockClose = vi.fn();
const mockDelete = vi.fn().mockResolvedValue({});

vi.mock('@/features/workspaces/hooks', () => ({
  useDeleteWorkspace: () => ({ mutateAsync: mockDelete, isPending: false }),
}));

vi.mock('@/features/workspaces/store', () => ({
  useWorkspacesStore: () => ({
    confirmDeleteId: 'ws-1',
    confirmDeleteName: 'prod-workspace',
    closeConfirmDelete: mockClose,
  }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient();
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('DeleteConfirmDialog', () => {
  it('renders when confirmDeleteId is set', () => {
    render(<DeleteConfirmDialog />, { wrapper });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('shows the workspace name in prompt', () => {
    render(<DeleteConfirmDialog />, { wrapper });
    // name appears both in paragraph and label
    expect(screen.getAllByText('prod-workspace').length).toBeGreaterThan(0);
  });

  it('Delete button is disabled when input is empty', () => {
    render(<DeleteConfirmDialog />, { wrapper });
    const btn = screen.getByRole('button', { name: /delete workspace/i });
    expect(btn).toBeDisabled();
  });

  it('Delete button is disabled when input does not match name', async () => {
    render(<DeleteConfirmDialog />, { wrapper });
    await userEvent.type(screen.getByRole('textbox'), 'wrong-name');
    expect(screen.getByRole('button', { name: /delete workspace/i })).toBeDisabled();
  });

  it('shows mismatch error when typed name is wrong', async () => {
    render(<DeleteConfirmDialog />, { wrapper });
    await userEvent.type(screen.getByRole('textbox'), 'wrong');
    expect(screen.getByText(/name does not match/i)).toBeInTheDocument();
  });

  it('Delete button enabled when input matches name exactly', async () => {
    render(<DeleteConfirmDialog />, { wrapper });
    await userEvent.type(screen.getByRole('textbox'), 'prod-workspace');
    expect(screen.getByRole('button', { name: /delete workspace/i })).not.toBeDisabled();
  });

  it('Cancel button calls closeConfirmDelete', async () => {
    render(<DeleteConfirmDialog />, { wrapper });
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });
});
