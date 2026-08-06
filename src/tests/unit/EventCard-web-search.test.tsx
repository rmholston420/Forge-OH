/**
 * src/tests/unit/EventCard-web-search.test.tsx
 *
 * Stage 6.1 — asserts the EventCard renders the magnifier icon for
 * web_search events and displays the summary text produced by
 * bff/services/event_normalize.py :: _web_search_summary.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EventCard } from '@/components/domain/EventCard';
import type { ToolEvent } from '@/lib/schemas/event';

function makeEvent(overrides: Partial<ToolEvent> = {}): ToolEvent {
  return {
    id: 'ws-1',
    type: 'web_search',
    timestamp: '2026-08-06T04:00:00Z',
    summary: 'Web searched: "colossus rtx 5090" — 3 result(s)',
    ...overrides,
  } as ToolEvent;
}

describe('EventCard — web_search variant', () => {
  it('renders the magnifier icon for web_search', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.getByText('🔍')).toBeInTheDocument();
  });

  it('renders the projected summary text', () => {
    render(<EventCard event={makeEvent()} />);
    expect(
      screen.getByText(/Web searched: "colossus rtx 5090" — 3 result\(s\)/),
    ).toBeInTheDocument();
  });

  it('does not render the LSP badge for web_search', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.queryByTestId('event-lsp-badge')).not.toBeInTheDocument();
  });
});
