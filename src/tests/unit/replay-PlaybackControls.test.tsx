/**
 * src/tests/unit/replay-PlaybackControls.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PlaybackControls } from '@/features/run-replay/PlaybackControls';
import type { PlaybackSpeed } from '@/features/run-replay/schemas';

const base = {
  isPlaying: false,
  speed: 1 as PlaybackSpeed,
  isLooping: false,
  currentIndex: 5,
  totalEvents: 20,
  onPlay: vi.fn(),
  onPause: vi.fn(),
  onStepBack: vi.fn(),
  onStepForward: vi.fn(),
  onJumpStart: vi.fn(),
  onJumpEnd: vi.fn(),
  onSetSpeed: vi.fn(),
  onSetLooping: vi.fn(),
};

describe('PlaybackControls', () => {
  it('has role=toolbar', () => {
    render(<PlaybackControls {...base} />);
    expect(screen.getByRole('toolbar')).toBeInTheDocument();
  });

  it('shows Play button when not playing', () => {
    render(<PlaybackControls {...base} isPlaying={false} />);
    expect(screen.getByLabelText('Play')).toBeInTheDocument();
  });

  it('shows Pause button when playing', () => {
    render(<PlaybackControls {...base} isPlaying />);
    expect(screen.getByLabelText('Pause')).toBeInTheDocument();
  });

  it('calls onPlay when Play is clicked', async () => {
    const onPlay = vi.fn();
    render(<PlaybackControls {...base} onPlay={onPlay} />);
    await userEvent.click(screen.getByLabelText('Play'));
    expect(onPlay).toHaveBeenCalledOnce();
  });

  it('calls onPause when Pause is clicked', async () => {
    const onPause = vi.fn();
    render(<PlaybackControls {...base} isPlaying onPause={onPause} />);
    await userEvent.click(screen.getByLabelText('Pause'));
    expect(onPause).toHaveBeenCalledOnce();
  });

  it('Step back disabled at start (currentIndex=0)', () => {
    render(<PlaybackControls {...base} currentIndex={0} />);
    expect(screen.getByLabelText('Step back')).toBeDisabled();
  });

  it('Step forward disabled at end', () => {
    render(<PlaybackControls {...base} currentIndex={19} totalEvents={20} />);
    expect(screen.getByLabelText('Step forward')).toBeDisabled();
  });

  it('Jump to start disabled at start', () => {
    render(<PlaybackControls {...base} currentIndex={0} />);
    expect(screen.getByLabelText('Jump to start')).toBeDisabled();
  });

  it('active speed button has aria-pressed=true', () => {
    render(<PlaybackControls {...base} speed={2 as PlaybackSpeed} />);
    const btn2x = screen.getByRole('button', { name: '2x' });
    expect(btn2x).toHaveAttribute('aria-pressed', 'true');
  });

  it('inactive speed button has aria-pressed=false', () => {
    render(<PlaybackControls {...base} speed={1 as PlaybackSpeed} />);
    const btn2x = screen.getByRole('button', { name: '2x' });
    expect(btn2x).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls onSetSpeed with correct value', async () => {
    const onSetSpeed = vi.fn();
    render(<PlaybackControls {...base} onSetSpeed={onSetSpeed} />);
    await userEvent.click(screen.getByRole('button', { name: '4x' }));
    expect(onSetSpeed).toHaveBeenCalledWith(4);
  });

  it('loop button aria-pressed reflects isLooping', () => {
    render(<PlaybackControls {...base} isLooping />);
    expect(screen.getByLabelText('Loop playback')).toHaveAttribute('aria-pressed', 'true');
  });

  it('loop toggle calls onSetLooping with inverted value', async () => {
    const onSetLooping = vi.fn();
    render(<PlaybackControls {...base} isLooping={false} onSetLooping={onSetLooping} />);
    await userEvent.click(screen.getByLabelText('Loop playback'));
    expect(onSetLooping).toHaveBeenCalledWith(true);
  });
});
