import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('./hooks', () => ({
  useResetWorkspace:  () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteWorkspace: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/components/auth/CanDo', () => ({
  CanDo: ({ children }: any) => <>{children}</>,
}));
vi.mock('./store', () => ({
  useWorkspacesStore: () => ({
    openEditDrawer: vi.fn(), openConfirmDelete: vi.fn(),
  }),
}));

import { WorkspaceCard } from '@/features/workspaces/WorkspaceCard';

const MOCK_WS = {
  id: 'ws-1', name: 'Test WS', type: 'docker' as const,
  status: 'idle' as const, runCount: 5,
  diskUsageMb: 512, diskLimitMb: 2048,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  envVars: [],
};

describe('WorkspaceCard', () => {
  it('renders workspace name and type badge', () => {
    render(<WorkspaceCard workspace={MOCK_WS} />);
    expect(screen.getByText('Test WS')).toBeInTheDocument();
    expect(screen.getByText('docker')).toBeInTheDocument();
  });

  it('shows disk usage progress', () => {
    render(<WorkspaceCard workspace={MOCK_WS} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('value', '25'); // 512/2048 = 25%
  });

  it('shows Edit, Reset, Delete buttons', () => {
    render(<WorkspaceCard workspace={MOCK_WS} />);
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  it('disables Reset when workspace is active', () => {
    render(<WorkspaceCard workspace={{ ...MOCK_WS, status: 'active' }} />);
    expect(screen.getByRole('button', { name: /reset/i })).toBeDisabled();
  });
});
