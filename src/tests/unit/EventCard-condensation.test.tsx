/**
 * src/tests/unit/EventCard-condensation.test.tsx
 *
 * Stage 6.2 — asserts the EventCard renders the compression icon (🗜️)
 * for all three condensation-family event types produced by
 * bff/services/event_normalize.py:
 *   - "condensation"          (SDK Condensation)
 *   - "condensation_request"  (SDK CondensationRequest)
 *   - "condensation_summary"  (SDK CondensationSummaryEvent)
 * and displays the projected summary text for each.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EventCard } from '@/components/domain/EventCard';
import type { ToolEvent } from '@/lib/schemas/event';

function makeEvent(type: string, summary: string, id: string): ToolEvent {
  return {
    id,
    type,
    timestamp: '2026-08-06T05:00:00Z',
    summary,
  } as ToolEvent;
}

describe('EventCard — condensation family', () => {
  it('renders the compression icon for type "condensation"', () => {
    render(
      <EventCard
        event={makeEvent(
          'condensation',
          'Context compressed — 3 turns forgotten',
          'c-1',
        )}
      />,
    );
    expect(screen.getByText('🗜️')).toBeInTheDocument();
    expect(
      screen.getByText(/Context compressed — 3 turns forgotten/),
    ).toBeInTheDocument();
  });

  it('renders the compression icon for type "condensation_request"', () => {
    render(
      <EventCard
        event={makeEvent(
          'condensation_request',
          'Condensation requested',
          'cr-1',
        )}
      />,
    );
    expect(screen.getByText('🗜️')).toBeInTheDocument();
    expect(screen.getByText(/Condensation requested/)).toBeInTheDocument();
  });

  it('renders the compression icon for type "condensation_summary"', () => {
    render(
      <EventCard
        event={makeEvent(
          'condensation_summary',
          'Compression summary — 3 prior turns rolled up.',
          'cs-1',
        )}
      />,
    );
    expect(screen.getByText('🗜️')).toBeInTheDocument();
    expect(
      screen.getByText(/Compression summary — 3 prior turns rolled up\./),
    ).toBeInTheDocument();
  });

  it('does not render the LSP badge for condensation events', () => {
    render(
      <EventCard
        event={makeEvent('condensation', 'Context compressed — 1 turn forgotten', 'c-2')}
      />,
    );
    expect(screen.queryByTestId('event-lsp-badge')).not.toBeInTheDocument();
  });
});
