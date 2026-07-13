import { create } from 'zustand';
import type { PlanNode } from '@/lib/schemas/plan';

interface PlanState {
  nodes: PlanNode[];
  setNodes: (nodes: PlanNode[]) => void;
  updateNodeStatus: (nodeId: string, status: PlanNode['status']) => void;
}

export const usePlanStore = create<PlanState>((set) => ({
  nodes: [],
  setNodes: (nodes) => set({ nodes }),
  updateNodeStatus: (nodeId, status) =>
    set((s) => ({
      nodes: s.nodes.map((n) => n.id === nodeId ? { ...n, status } : n),
    })),
}));
