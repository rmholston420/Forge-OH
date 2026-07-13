import { create } from 'zustand';

interface MCPUIState {
  selectedServerId: string | null;
  pingInFlight: Set<string>;
  selectedPluginId: string | null;
  configDrawerOpen: boolean;
  activeTab: 'mcp' | 'plugins';

  setSelectedServerId: (id: string | null) => void;
  setPingInFlight: (id: string, value: boolean) => void;
  openPluginConfig: (id: string) => void;
  closePluginConfig: () => void;
  setActiveTab: (tab: 'mcp' | 'plugins') => void;
}

export const useMCPStore = create<MCPUIState>((set) => ({
  selectedServerId: null,
  pingInFlight: new Set(),
  selectedPluginId: null,
  configDrawerOpen: false,
  activeTab: 'mcp',

  setSelectedServerId: (id) => set({ selectedServerId: id }),
  setPingInFlight: (id, value) =>
    set((state) => {
      const next = new Set(state.pingInFlight);
      value ? next.add(id) : next.delete(id);
      return { pingInFlight: next };
    }),
  openPluginConfig: (id) => set({ selectedPluginId: id, configDrawerOpen: true }),
  closePluginConfig: () => set({ configDrawerOpen: false, selectedPluginId: null }),
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
