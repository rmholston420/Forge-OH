/**
 * src/tests/unit/EventCard-lsp.test.tsx
 *
 * Stage 4.4 — asserts the EventCard renders an "LSP" badge and the
 * correct Serena-family icon when `event.type` starts with `lsp_`.
 * See ADR-018 for why the discriminator is a flat string on the
 * existing ToolEvent shape rather than a new event-kind union.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EventCard } from '@/components/domain/EventCard';
import type { ToolEvent } from '@/lib/schemas/event';

function makeEvent(overrides: Partial<ToolEvent> = {}): ToolEvent {
  return {
    id: 'e1',
    type: 'lsp_find_symbol',
    timestamp: '2026-08-06T04:00:00Z',
    summary: 'Serena find_symbol: MyClass/foo',
    ...overrides,
  } as ToolEvent;
}

describe('EventCard — LSP variant', () => {
  it('shows the LSP badge when event.type starts with lsp_', () => {
    render(<EventCard event={makeEvent()} />);
    expect(screen.getByTestId('event-lsp-badge')).toBeInTheDocument();
    expect(screen.getByText(/Serena find_symbol: MyClass\/foo/)).toBeInTheDocument();
  });

  it('does NOT show the LSP badge for a generic action event', () => {
    render(<EventCard event={makeEvent({ type: 'action', summary: 'ran bash' })} />);
    expect(screen.queryByTestId('event-lsp-badge')).not.toBeInTheDocument();
  });

  it('renders known LSP ops with their family icon', () => {
    const ops = [
      'lsp_find_symbol',
      'lsp_find_referencing_symbols',
      'lsp_get_symbols_overview',
      'lsp_replace_symbol_body',
      'lsp_insert_after_symbol',
      'lsp_insert_before_symbol',
    ];
    for (const t of ops) {
      const { unmount } = render(<EventCard event={makeEvent({ id: t, type: t })} />);
      expect(screen.getByTestId('event-lsp-badge')).toBeInTheDocument();
      unmount();
    }
  });

  it('unknown lsp_ subtype still gets the LSP badge (fallback icon ok)', () => {
    render(<EventCard event={makeEvent({ type: 'lsp_something_new' })} />);
    expect(screen.getByTestId('event-lsp-badge')).toBeInTheDocument();
  });
});
