import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('./hooks', () => ({
  usePingMcpServer:   () => ({ mutate: vi.fn(), isPending: false }),
  useToggleMcpServer: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteMcpServer: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/components/auth/CanDo', () => ({ CanDo: ({ children }: any) => <>{children}</> }));
vi.mock('./store', () => ({ useMcpStore: () => ({ setConfirmDeleteId: vi.fn() }) }));

import { McpServerCard } from '@/features/mcp/McpServerCard';

const MOCK_SERVER = {
  id: 'mcp-1', name: 'Filesystem', transport: 'stdio' as const,
  status: 'connected' as const, toolCount: 8, tags: ['files'],
  enabled: true, lastPingMs: 12,
};

describe('McpServerCard', () => {
  it('renders name, status badge, tool count', () => {
    render(<McpServerCard server={MOCK_SERVER} />);
    expect(screen.getByText('Filesystem')).toBeInTheDocument();
    expect(screen.getByText('connected')).toBeInTheDocument();
    expect(screen.getByText('8 tools')).toBeInTheDocument();
  });

  it('renders latency when present', () => {
    render(<McpServerCard server={MOCK_SERVER} />);
    expect(screen.getByText('12ms')).toBeInTheDocument();
  });

  it('shows Enable instead of Disable when disabled', () => {
    render(<McpServerCard server={{ ...MOCK_SERVER, enabled: false }} />);
    expect(screen.getByRole('button', { name: /enable/i })).toBeInTheDocument();
  });

  it('renders tags', () => {
    render(<McpServerCard server={MOCK_SERVER} />);
    expect(screen.getByText('files')).toBeInTheDocument();
  });
});
