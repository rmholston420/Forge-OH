import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserViewer } from '@/components/domain/BrowserViewer';
import type { BrowserFrame } from '@/lib/schemas/browser';

const makeFrame = (i: number, action: BrowserFrame['action'] = 'navigate'): BrowserFrame => ({
  id: `f-${i}`, runId: 'run-1', seq: i, action,
  url: `https://example.com/${i}`, screenshotUrl: null,
  selector: null, value: null, boundingBox: null,
  durationMs: 100, error: null,
  timestamp: new Date().toISOString(),
});

describe('BrowserViewer', () => {
  it('renders empty state with no frames', () => {
    render(<BrowserViewer frames={[]} />);
    expect(screen.getByText(/No browser activity/)).toBeTruthy();
  });

  it('shows frame count in controls', () => {
    const frames = [makeFrame(0), makeFrame(1), makeFrame(2)];
    render(<BrowserViewer frames={frames} />);
    expect(screen.getByText('1 / 3')).toBeTruthy();
  });

  it('advances playhead on next-frame click', () => {
    const frames = [makeFrame(0), makeFrame(1), makeFrame(2)];
    render(<BrowserViewer frames={frames} />);
    fireEvent.click(screen.getByLabelText('Next frame'));
    expect(screen.getByText('2 / 3')).toBeTruthy();
  });

  it('renders timeline items', () => {
    const frames = [makeFrame(0, 'click'), makeFrame(1, 'type')];
    render(<BrowserViewer frames={frames} />);
    expect(screen.getAllByRole('button', { name: /frame/i })).toBeTruthy();
  });
});
