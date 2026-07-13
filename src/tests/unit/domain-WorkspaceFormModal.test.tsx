/**
 * src/tests/unit/domain-WorkspaceFormModal.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceFormModal } from '@/components/domain/WorkspaceFormModal';

vi.mock('@/features/workspaces/hooks', () => ({
  useCreateWorkspace: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useUpdateWorkspace: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useWorkspace: () => ({ data: undefined }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('WorkspaceFormModal', () => {
  it('renders null when open=false', () => {
    const { container } = render(<WorkspaceFormModal open={false} onClose={vi.fn()} />, { wrapper });
    expect(container.firstChild).toBeNull();
  });

  it('shows "New Workspace" title in create mode', () => {
    render(<WorkspaceFormModal open onClose={vi.fn()} />, { wrapper });
    expect(screen.getByText('New Workspace')).toBeInTheDocument();
  });

  it('shows "Edit Workspace" title in edit mode', () => {
    render(<WorkspaceFormModal open onClose={vi.fn()} editingId="ws-1" />, { wrapper });
    expect(screen.getByText('Edit Workspace')).toBeInTheDocument();
  });

  it('has role=dialog', () => {
    render(<WorkspaceFormModal open onClose={vi.fn()} />, { wrapper });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('Name field is present', () => {
    render(<WorkspaceFormModal open onClose={vi.fn()} />, { wrapper });
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it('Type selector renders three options', () => {
    render(<WorkspaceFormModal open onClose={vi.fn()} />, { wrapper });
    const select = screen.getByLabelText(/type/i);
    expect(select.querySelectorAll('option')).toHaveLength(3);
  });

  it('Escape key calls onClose', () => {
    const onClose = vi.fn();
    render(<WorkspaceFormModal open onClose={onClose} />, { wrapper });
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('inner content click does NOT call onClose', async () => {
    const onClose = vi.fn();
    render(<WorkspaceFormModal open onClose={onClose} />, { wrapper });
    await userEvent.click(screen.getByLabelText(/name/i));
    expect(onClose).not.toHaveBeenCalled();
  });
});
