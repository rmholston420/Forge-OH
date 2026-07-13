import type { RunEvent } from '@/features/run-detail/schemas';
import type { PlanNode } from '@/features/plan/schemas';

/**
 * Pure function: replay plan_node_* events up to `upToIndex`
 * and return the reconstructed plan node array at that point in time.
 */
export function derivePlanState(events: RunEvent[], upToIndex: number): PlanNode[] {
  const nodes = new Map<string, PlanNode>();

  const slice = events.slice(0, upToIndex + 1);

  for (const event of slice) {
    if (event.type === 'plan_node_created') {
      const payload = event.payload as any;
      nodes.set(payload.id, {
        id:       payload.id,
        title:    payload.title,
        status:   'queued',
        children: [],
        parentId: payload.parentId,
      });
    } else if (event.type === 'plan_node_status_updated') {
      const payload = event.payload as any;
      const existing = nodes.get(payload.id);
      if (existing) {
        nodes.set(payload.id, { ...existing, status: payload.status });
      }
    }
  }

  // Build tree from flat map
  const roots: PlanNode[] = [];
  for (const node of nodes.values()) {
    if (!node.parentId) {
      roots.push(node);
    } else {
      const parent = nodes.get(node.parentId);
      if (parent) {
        parent.children = [...(parent.children ?? []), node];
      }
    }
  }
  return roots;
}
