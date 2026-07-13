/**
 * src/tests/unit/replay-ReplayTimeline.test.tsx
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReplayTimeline } from '@/features/run-replay/ReplayTimeline';

const base = {
  totalEvents: 50,
  currentIndex: 10,
  onScrub: vi.fn(),
  onStepBack: vi.fn(),
  onStepForward: vi.fn(),
};

describe('ReplayTimeline', () => {
  it('renders a range input', () => {
    render(<ReplayTimeline {...base} />);
    expect(screen.getByRole('slider')).toBeInTheDocument();
  });

  it('range min=0 and max=totalEvents-1', () => {
    render(<ReplayTimeline {...base} />);
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '49');
  });

  it('range value matches currentIndex', () => {
    render(<ReplayTimeline {...base} currentIndex={7} />);
    expect(screen.getByRole('slider')).toHaveAttribute('aria-valuenow', '7');
  });

  it('renders counter text', () => {
    render(<ReplayTimeline {...base} />);
    expect(screen.getByText('11 / 50')).toBeInTheDocument();
  });

  it('renders timestamp when provided', () => {
    render(<ReplayTimeline {...base} currentTimestamp="2026-01-01T12:00:00Z" />);
    const time = document.querySelector('time');
    expect(time).not.toBeNull();
    expect(time!.getAttribute('dateTime')).toBe('2026-01-01T12:00:00Z');
  });

  it('does not render time element when timestamp omitted', () => {
    render(<ReplayTimeline {...base} />);
    expect(document.querySelector('time')).toBeNull();
  });

  it('ArrowLeft calls onStepBack', () => {
    const onStepBack = vi.fn();
    render(<ReplayTimeline {...base} onStepBack={onStepBack} />);
    fireEvent.keyDown(window, { key: 'ArrowLeft' });
    expect(onStepBack).toHaveBeenCalled();
  });

  it('ArrowRight calls onStepForward', () => {
    const onStepForward = vi.fn();
    render(<ReplayTimeline {...base} onStepForward={onStepForward} />);
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(onStepForward).toHaveBeenCalled();
  });

  it('Shift+ArrowLeft calls onScrub with currentIndex-10', () => {
    const onScrub = vi.fn();
    render(<ReplayTimeline {...base} currentIndex={15} onScrub={onScrub} />);
    fireEvent.keyDown(window, { key: 'ArrowLeft', shiftKey: true });
    expect(onScrub).toHaveBeenCalledWith(5);
  });
});
