/**
 * src/tests/unit/domain-RunDetailHeader.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RunDetailHeader } from '@/components/domain/RunDetailHeader';
import type { RunSummary } from '@/lib/schemas/run';

const baseRun: RunSummary = {
  id: 'run-1',
  title: 'My test run',
  status: 'running',
  workspaceType: 'local',
  agentPresetName: 'Claude 3.5',
  elapsedMs: 4200,
  estimatedCostUsd: 0.012,
  activeTool: null,
  createdAt: '2026-01-01T00:00:00Z',
};

describe('RunDetailHeader', () => {
  it('renders the run title', () => {
    render(<RunDetailHeader run={baseRun} />);
    expect(screen.getByText('My test run')).toBeInTheDocument();
  });

  it('renders the status badge', () => {
    render(<RunDetailHeader run={baseRun} />);
    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('Fork button is always rendered', () => {
    render(<RunDetailHeader run={baseRun} onFork={vi.fn()} />);
    expect(screen.getByLabelText('Fork run')).toBeInTheDocument();
  });

  it('Pause button is shown for running status', () => {
    render(<RunDetailHeader run={baseRun} onPause={vi.fn()} />);
    expect(screen.getByLabelText('Pause run')).toBeInTheDocument();
  });

  it('Resume label shown when status=paused', () => {
    render(<RunDetailHeader run={{ ...baseRun, status: 'paused' }} onPause={vi.fn()} />);
    expect(screen.getByLabelText('Resume run')).toBeInTheDocument();
  });

  it('Stop button is shown for running status', () => {
    render(<RunDetailHeader run={baseRun} onStop={vi.fn()} />);
    expect(screen.getByLabelText('Stop run')).toBeInTheDocument();
  });

  it('Pause/Stop NOT shown for terminal status', () => {
    render(<RunDetailHeader run={{ ...baseRun, status: 'succeeded' }} onPause={vi.fn()} onStop={vi.fn()} />);
    expect(screen.queryByLabelText('Pause run')).toBeNull();
    expect(screen.queryByLabelText('Stop run')).toBeNull();
  });

  it('Approve button is shown for awaiting_approval', () => {
    render(<RunDetailHeader run={{ ...baseRun, status: 'awaiting_approval' }} onApprove={vi.fn()} />);
    expect(screen.getByLabelText('Approve pending action')).toBeInTheDocument();
  });

  it('Approve button NOT shown for running status', () => {
    render(<RunDetailHeader run={baseRun} onApprove={vi.fn()} />);
    expect(screen.queryByLabelText('Approve pending action')).toBeNull();
  });

  it('onFork callback fires on click', async () => {
    const onFork = vi.fn();
    render(<RunDetailHeader run={baseRun} onFork={onFork} />);
    await userEvent.click(screen.getByLabelText('Fork run'));
    expect(onFork).toHaveBeenCalledOnce();
  });

  it('renders activeTool chip when activeTool is set', () => {
    render(<RunDetailHeader run={{ ...baseRun, activeTool: 'bash' }} />);
    expect(screen.getByText('bash')).toBeInTheDocument();
  });

  it('does not render activeTool chip when null', () => {
    render(<RunDetailHeader run={baseRun} />);
    // activeTool=null means no ⚡ chip
    expect(screen.queryByText('bash')).toBeNull();
  });
});
