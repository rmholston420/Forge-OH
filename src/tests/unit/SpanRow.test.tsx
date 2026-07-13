import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SpanRow } from '@/components/domain/SpanRow';
import type { Span } from '@/lib/schemas/trace';

const makeSpan = (overrides: Partial<Span> = {}): Span => ({
  spanId: 'span-1', traceId: 'trace-1', parentSpanId: null,
  name: 'root.op', status: 'ok',
  startTime: '2026-07-12T00:00:00Z', endTime: '2026-07-12T00:00:01Z',
  durationMs: 1000, attributes: {}, events: [], children: [],
  ...overrides,
});

describe('SpanRow', () => {
  it('renders span name', () => {
    render(<table><tbody>
      <SpanRow span={makeSpan()} depth={0} traceStartTime="2026-07-12T00:00:00Z" traceDurationMs={1000} />
    </tbody></table>);
    expect(screen.getByText('root.op')).toBeTruthy();
  });

  it('shows error status badge', () => {
    render(<table><tbody>
      <SpanRow span={makeSpan({ status: 'error' })} depth={0} traceStartTime="2026-07-12T00:00:00Z" traceDurationMs={1000} />
    </tbody></table>);
    expect(screen.getByText('error')).toBeTruthy();
  });

  it('shows expand button when span has children', () => {
    const parent = makeSpan({ children: [makeSpan({ spanId: 'child-1', name: 'child.op' })] });
    render(<table><tbody>
      <SpanRow span={parent} depth={0} traceStartTime="2026-07-12T00:00:00Z" traceDurationMs={1000} />
    </tbody></table>);
    expect(screen.getByLabelText('Expand')).toBeTruthy();
  });
});
