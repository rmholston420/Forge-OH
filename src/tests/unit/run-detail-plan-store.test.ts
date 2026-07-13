/**
 * src/tests/unit/run-detail-plan-store.test.ts
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { usePlanStore } from '@/features/run-detail/plan-store';
import type { PlanNode } from '@/lib/schemas/plan';

const makeNode = (id: string, status: PlanNode['status'] = 'queued'): PlanNode => ({
  id,
  title: `Step ${id}`,
  status,
  children: [],
});

beforeEach(() => usePlanStore.setState({ nodes: [] }));

describe('usePlanStore', () => {
  it('initial nodes is empty', () => {
    expect(usePlanStore.getState().nodes).toHaveLength(0);
  });

  it('setNodes replaces nodes list', () => {
    const nodes = [makeNode('n1'), makeNode('n2')];
    usePlanStore.getState().setNodes(nodes);
    expect(usePlanStore.getState().nodes).toHaveLength(2);
  });

  it('updateNodeStatus updates only matching node', () => {
    usePlanStore.getState().setNodes([makeNode('n1', 'queued'), makeNode('n2', 'queued')]);
    usePlanStore.getState().updateNodeStatus('n1', 'done');
    const nodes = usePlanStore.getState().nodes;
    expect(nodes.find(n => n.id === 'n1')!.status).toBe('done');
    expect(nodes.find(n => n.id === 'n2')!.status).toBe('queued');
  });

  it('updateNodeStatus with unknown id does not mutate any node', () => {
    usePlanStore.getState().setNodes([makeNode('n1', 'active')]);
    usePlanStore.getState().updateNodeStatus('nonexistent', 'done');
    expect(usePlanStore.getState().nodes[0].status).toBe('active');
  });
});
