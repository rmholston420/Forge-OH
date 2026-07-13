import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkspaceCard } from '@/components/domain/WorkspaceCard';

const ws = {
  id: 'ws-1', name: 'my-workspace', type: 'local' as const,
  status: 'active' as const, description: 'Test WS',
  baseDir: '/home/test', dockerImage: null, remoteUrl: null,
  envVars: {}, createdAt: '2026-07-12T00:00:00Z', updatedAt: '2026-07-12T00:00:00Z',
  lastUsedAt: null, activeRunCount: 0,
};

describe('WorkspaceCard', () => {
  it('renders workspace name', () => {
    render(<WorkspaceCard workspace={ws} />);
    expect(screen.getByText('my-workspace')).toBeTruthy();
  });

  it('shows type badge', () => {
    render(<WorkspaceCard workspace={ws} />);
    expect(screen.getByText('Local')).toBeTruthy();
  });

  it('delete button disabled when runs active', () => {
    render(<WorkspaceCard workspace={{ ...ws, activeRunCount: 2 }} />);
    const deleteBtn = screen.getByRole('button', { name: /Delete/ });
    expect(deleteBtn.hasAttribute('disabled')).toBe(true);
  });

  it('calls onEdit when edit clicked', () => {
    const onEdit = vi.fn();
    render(<WorkspaceCard workspace={ws} onEdit={onEdit} />);
    screen.getByRole('button', { name: /Edit/ }).click();
    expect(onEdit).toHaveBeenCalledWith('ws-1');
  });
});
