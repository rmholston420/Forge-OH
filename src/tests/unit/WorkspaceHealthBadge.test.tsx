import { render, screen } from '@testing-library/react';
import { WorkspaceHealthBadge } from '@/components/domain/workspace-health-badge';
import { describe, it, expect } from 'vitest';

describe('WorkspaceHealthBadge', () => {
  it.each([
    ['healthy', 'Healthy'],
    ['warning', 'Warning'],
    ['error', 'Error'],
    ['disconnected', 'Disconnected'],
  ] as const)('renders text label for %s — not color alone', (health, label) => {
    render(<WorkspaceHealthBadge health={health} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByRole('status')).toBeTruthy();
  });
});
