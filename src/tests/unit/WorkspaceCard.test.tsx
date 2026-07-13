import { render, screen, fireEvent } from '@testing-library/react';
import { WorkspaceCard } from '@/components/domain/workspace-card';
import type { Workspace } from '@/features/workspaces/schemas';
import { describe, it, expect, vi } from 'vitest';

const BASE: Workspace = {
  id: 'ws-1',
  name: 'My Workspace',
  type: 'docker',
  health: 'healthy',
  isolationMode: 'isolated',
  runCount: 5,
  activeRunId: null,
  lastSeenAt: new Date().toISOString(),
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

describe('WorkspaceCard', () => {
  it('renders name and type badge', () => {
    render(<WorkspaceCard workspace={BASE} />);
    expect(screen.getByText('My Workspace')).toBeTruthy();
    expect(screen.getByText('Docker')).toBeTruthy();
  });

  it('shows Healthy badge with text label', () => {
    render(<WorkspaceCard workspace={BASE} />);
    expect(screen.getByText('Healthy')).toBeTruthy();
  });

  it('calls onSelect when clicked', () => {
    const onSelect = vi.fn();
    render(<WorkspaceCard workspace={BASE} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('article'));
    expect(onSelect).toHaveBeenCalledWith('ws-1');
  });

  it('does not propagate reset click to card select', () => {
    const onSelect = vi.fn();
    const onReset = vi.fn();
    render(<WorkspaceCard workspace={BASE} onSelect={onSelect} onReset={onReset} />);
    fireEvent.click(screen.getByLabelText('Reset workspace My Workspace'));
    expect(onReset).toHaveBeenCalledWith('ws-1');
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('shows active run dot when activeRunId is set', () => {
    render(<WorkspaceCard workspace={{ ...BASE, activeRunId: 'run-42' }} />);
    expect(screen.getByLabelText('Active run')).toBeTruthy();
  });
});
