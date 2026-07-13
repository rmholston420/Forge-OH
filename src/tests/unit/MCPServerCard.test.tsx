import { render, screen, fireEvent } from '@testing-library/react';
import { MCPServerCard } from '@/components/domain/mcp-server-card';
import type { MCPServer } from '@/features/mcp/schemas';
import { describe, it, expect, vi } from 'vitest';

const BASE: MCPServer = {
  id: 'mcp-1',
  name: 'Test MCP',
  url: 'http://localhost:3001',
  status: 'connected',
  toolCount: 5,
  lastPingMs: 3.2,
  lastPingAt: new Date().toISOString(),
};

describe('MCPServerCard', () => {
  it('renders name and status with text label (not color-only)', () => {
    render(
      <MCPServerCard server={BASE} pingInFlight={false} onToggle={vi.fn()} onPing={vi.fn()} />,
    );
    expect(screen.getByText('Test MCP')).toBeTruthy();
    expect(screen.getByText('Connected')).toBeTruthy();
  });

  it('calls onPing with correct id', () => {
    const onPing = vi.fn();
    render(
      <MCPServerCard server={BASE} pingInFlight={false} onToggle={vi.fn()} onPing={onPing} />,
    );
    fireEvent.click(screen.getByLabelText('Ping MCP server Test MCP'));
    expect(onPing).toHaveBeenCalledWith('mcp-1');
  });

  it('disables ping button while in flight', () => {
    render(
      <MCPServerCard server={BASE} pingInFlight={true} onToggle={vi.fn()} onPing={vi.fn()} />,
    );
    expect(screen.getByText('Pinging…').closest('button')).toBeDisabled();
  });

  it('calls onToggle(id, false) when toggled off', () => {
    const onToggle = vi.fn();
    render(
      <MCPServerCard server={BASE} pingInFlight={false} onToggle={onToggle} onPing={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledWith('mcp-1', false);
  });
});
