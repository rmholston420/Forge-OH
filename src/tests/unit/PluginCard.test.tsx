import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PluginCard } from '@/components/domain/PluginCard';

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

const plugin = {
  id: 'p-1', name: 'github-mcp', version: '1.2.0',
  description: 'GitHub integration', author: null,
  transport: 'stdio' as const, status: 'enabled' as const,
  capabilities: ['tools' as const], command: 'npx @github/mcp-server',
  url: null, envVars: {}, toolCount: 12,
  installedAt: '2026-07-12T00:00:00Z', lastHeartbeatAt: null,
};

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={qc}>{children}</QueryClientProvider>
);

describe('PluginCard', () => {
  it('renders plugin name and version', () => {
    render(<PluginCard plugin={plugin} />, { wrapper });
    expect(screen.getByText('github-mcp')).toBeTruthy();
    expect(screen.getByText('v1.2.0')).toBeTruthy();
  });

  it('renders toggle in pressed state for enabled plugin', () => {
    render(<PluginCard plugin={plugin} />, { wrapper });
    const toggle = screen.getByRole('button', { name: /Disable/ });
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });
});
