/**
 * src/tests/unit/domain-PlanNode.test.tsx
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlanNodeItem } from '@/components/domain/PlanNode';
import type { PlanNode } from '@/lib/schemas/plan';

const makeNode = (overrides: Partial<PlanNode> = {}): PlanNode => ({
  id: 'node-1',
  title: 'Install dependencies',
  status: 'queued',
  children: [],
  ...overrides,
});

describe('PlanNodeItem', () => {
  it.each([
    ['queued', 'Queued'],
    ['active', 'Active'],
    ['done', 'Done'],
    ['failed', 'Failed'],
    ['blocked', 'Blocked'],
    ['awaiting_approval', 'Awaiting Approval'],
  ] as [PlanNode['status'], string][])('status=%s shows label=%s', (status, label) => {
    render(<ul><PlanNodeItem node={makeNode({ status })} /></ul>);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('renders the node title', () => {
    render(<ul><PlanNodeItem node={makeNode({ title: 'Run tests' })} /></ul>);
    expect(screen.getByText('Run tests')).toBeInTheDocument();
  });

  it('renders children recursively', () => {
    const node = makeNode({
      children: [
        makeNode({ id: 'child-1', title: 'Child step', status: 'done' }),
      ],
    });
    render(<ul><PlanNodeItem node={node} /></ul>);
    expect(screen.getByText('Child step')).toBeInTheDocument();
  });

  it('applies depth padding for nested nodes', () => {
    const { container } = render(<ul><PlanNodeItem node={makeNode()} depth={2} /></ul>);
    const li = container.querySelector('li')!;
    expect(li.style.paddingLeft).toBe('32px');
  });

  it('no paddingLeft at depth 0 (default)', () => {
    const { container } = render(<ul><PlanNodeItem node={makeNode()} /></ul>);
    const li = container.querySelector('li')!;
    // paddingLeft should be empty or 0 — not set
    expect(li.style.paddingLeft).toBeFalsy();
  });

  it('does not render children list when children is empty', () => {
    const { container } = render(<ul><PlanNodeItem node={makeNode({ children: [] })} /></ul>);
    expect(container.querySelectorAll('ul')).toHaveLength(0);
  });
});
