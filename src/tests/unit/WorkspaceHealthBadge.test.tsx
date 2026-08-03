import { render, screen } from '@/tests/helpers/render';
import { WorkspaceHealthBadge } from '@/components/domain/workspace-health-badge';
import { describe, it, expect } from 'vitest';

describe('WorkspaceHealthBadge', () => {
  it.each([
    ['healthy',  'Healthy'],
    ['degraded', 'Degraded'],
    ['offline',  'Offline'],
    ['unknown',  'Unknown'],
  ] as const)('renders text label for %s — not color alone', (health, label) => {
    render(<WorkspaceHealthBadge health={health} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByRole('status')).toBeTruthy();
  });
});
