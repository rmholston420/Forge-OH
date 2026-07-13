import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('./hooks', () => ({
  useSetDefaultPreset: () => ({ mutate: vi.fn(), isPending: false }),
  useDuplicatePreset:  () => ({ mutate: vi.fn(), isPending: false }),
  useDeletePreset:     () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock('@/components/auth/CanDo', () => ({ CanDo: ({ children }: any) => <>{children}</> }));
vi.mock('./store', () => ({
  useAgentPresetStore: () => ({ openEditDrawer: vi.fn(), setConfirmDelete: vi.fn() }),
}));

import { AgentPresetCard } from '@/features/agent-presets/AgentPresetCard';
import type { AgentPreset } from '@/features/agent-presets/schemas';

const BASE: AgentPreset = {
  id: 'ap-1', name: 'General Dev', model: 'gpt-4o',
  maxSteps: 150, maxCost: 8.0, temperature: 0.2, topP: 0.95,
  toolAllowlist: ['bash', 'browser'], systemPrompt: '',
  loopGuard: { enabled: true, windowSize: 20, threshold: 3 },
  isDefault: false, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
};

describe('AgentPresetCard', () => {
  it('renders name and model badge', () => {
    render(<AgentPresetCard preset={BASE} />);
    expect(screen.getByText('General Dev')).toBeInTheDocument();
    expect(screen.getByText('GPT-4o')).toBeInTheDocument();
  });

  it('shows Default star badge when isDefault=true', () => {
    render(<AgentPresetCard preset={{ ...BASE, isDefault: true }} />);
    expect(screen.getByText(/default/i)).toBeInTheDocument();
  });

  it('shows loop guard indicator when enabled', () => {
    render(<AgentPresetCard preset={BASE} />);
    expect(screen.getByText(/loop guard/i)).toBeInTheDocument();
  });

  it('disables delete button on default preset', () => {
    render(<AgentPresetCard preset={{ ...BASE, isDefault: true }} />);
    expect(screen.getByRole('button', { name: /delete/i })).toBeDisabled();
  });

  it('renders tool count', () => {
    render(<AgentPresetCard preset={BASE} />);
    expect(screen.getByText('2 tools')).toBeInTheDocument();
  });
});
