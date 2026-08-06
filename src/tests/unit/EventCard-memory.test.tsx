/**
 * src/tests/unit/EventCard-memory.test.tsx
 *
 * Stage 5.6a / ADR-024 — asserts the EventCard renders the brain icon
 * for memory_consultation events and displays the summary text
 * produced by bff/services/event_normalize.py :: _memory_consultation_summary.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EventCard } from '@/components/domain/EventCard';
import type { ToolEvent } from '@/lib/schemas/event';

function makeEvent(overrides: Partial<ToolEvent> = {}): ToolEvent {
  return {
    id: 'mem-1',
    type: 'memory_consultation',
    timestamp: '2026-08-06T04:00:00Z',
    summary: 'Memory consulted (semantic): "colossus" — 3 result(s)',
    ...overrides,
  } as ToolEvent;
}

describe('EventCard — memory_consultation variant', () => {
  it('renders the brain icon for memory_consultation', () => {
    render(<EventCard event={makeEvent()} />);
    // Icon is a leading emoji glyph rendered as text.
    expect(screen.getByText('🧠')).toBeInTheDocument();
  });

  it('renders the projected summary text', () => {
    render(<EventCard event={makeEvent()} />);
    expect(
      screen.getByText(/Memory consulted \(semantic\): "colossus" — 3 result\(s\)/),
    ).toBeInTheDocument();
  });

  it('does not render the LSP badge for memory_consultation', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.queryByTestId('event-lsp-badge')).not.toBeInTheDocument();
  });
});
