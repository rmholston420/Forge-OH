/**
 * Zustand store for Rigpa-LMS plugin session state.
 * Holds the current RigpaAgentLaunchContext and ribbon visibility.
 */
import { create } from 'zustand';
import type { RigpaAgentLaunchContext } from '@/lib/schemas/rigpa-lms';

interface RigpaLmsState {
  context: RigpaAgentLaunchContext | null;
  ribbonVisible: boolean;
  pluginMode: boolean;
  setContext: (ctx: RigpaAgentLaunchContext) => void;
  clearContext: () => void;
  setRibbonVisible: (v: boolean) => void;
  setPluginMode: (v: boolean) => void;
}

export const rigpaLmsStore = create<RigpaLmsState>((set) => ({
  context: null,
  ribbonVisible: false,
  pluginMode: false,
  setContext: (ctx) => set({ context: ctx, ribbonVisible: true }),
  clearContext: () => set({ context: null, ribbonVisible: false }),
  setRibbonVisible: (v) => set({ ribbonVisible: v }),
  setPluginMode: (v) => set({ pluginMode: v }),
}));

export const useRigpaLmsStore = rigpaLmsStore;
