import { derivePlanState } from '@/features/run-replay/derivePlanState';
import type { RunEvent } from '@/features/run-detail/schemas';

const makeEvent = (type: string, payload: object, idx: number): RunEvent => ({
  id: `evt-${idx}`, type: type as any, payload, timestamp: new Date().toISOString(),
  sequenceId: idx, runId: 'run-1',
});

const EVENTS: RunEvent[] = [
  makeEvent('plan_node_created',       { id: 'n1', title: 'Step 1', parentId: null }, 0),
  makeEvent('plan_node_created',       { id: 'n2', title: 'Step 2', parentId: null }, 1),
  makeEvent('plan_node_status_updated', { id: 'n1', status: 'active' },               2),
  makeEvent('plan_node_status_updated', { id: 'n1', status: 'done'   },               3),
  makeEvent('plan_node_status_updated', { id: 'n2', status: 'active' },               4),
];

describe('derivePlanState', () => {
  it('returns empty array for no events', () => {
    expect(derivePlanState([], 0)).toEqual([]);
  });

  it('creates nodes from plan_node_created events', () => {
    const nodes = derivePlanState(EVENTS, 1);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].title).toBe('Step 1');
  });

  it('applies status updates at correct index', () => {
    const nodes = derivePlanState(EVENTS, 2);
    const n1 = nodes.find(n => n.id === 'n1');
    expect(n1?.status).toBe('active');
  });

  it('progresses status correctly to done', () => {
    const nodes = derivePlanState(EVENTS, 3);
    expect(nodes.find(n => n.id === 'n1')?.status).toBe('done');
  });

  it('n2 is still queued at index 3', () => {
    const nodes = derivePlanState(EVENTS, 3);
    expect(nodes.find(n => n.id === 'n2')?.status).toBe('queued');
  });
});
