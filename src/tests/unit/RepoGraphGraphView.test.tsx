/**
 * src/tests/unit/RepoGraphGraphView.test.tsx
 *
 * Stage 4.3 — smoke test for the graph view. The real force-graph
 * library is browser-only and heavy; we mock it away and just verify
 * the component wires props through and renders its container.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { RepoGraphFullGraph } from '@/lib/schemas/repograph';

vi.mock('next/dynamic', () => ({
  default: () => {
    const Mocked = (props: Record<string, unknown>) => (
      <div data-testid="mocked-force-graph" data-node-count={String((props.graphData as { nodes: unknown[] } | undefined)?.nodes?.length ?? 0)} />
    );
    return Mocked;
  },
}));

import { RepoGraphGraphView } from '@/features/repograph/RepoGraphGraphView';

const FIXTURE: RepoGraphFullGraph = {
  repo_key: 'abc',
  nodes: [
    { id: 'file::m.py', kind: 'file', label: 'm.py', rel_path: 'm.py', language: 'python' },
    {
      id: 'sym::m.py::hello::1',
      kind: 'symbol',
      label: 'hello',
      rel_path: 'm.py',
      category: 'function',
      start_line: 1,
      end_line: 2,
      parent: null,
      pagerank: 0.42,
    },
  ],
  links: [
    { source: 'file::m.py', target: 'sym::m.py::hello::1', type: 'CONTAINS' },
  ],
  stats: { nodes: 2, symbols: 1, files: 1, edges: 1 },
};

describe('RepoGraphGraphView', () => {
  it('mounts with a container and forwards node count into the graph', () => {
    render(<RepoGraphGraphView graph={FIXTURE} />);
    expect(screen.getByTestId('repograph-graph-view')).toBeInTheDocument();
    expect(screen.getByTestId('mocked-force-graph').getAttribute('data-node-count')).toBe('2');
  });
});
