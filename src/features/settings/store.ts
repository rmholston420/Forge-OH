import { create } from 'zustand';

export type SettingsTab = 'appearance' | 'model' | 'shortcuts' | 'about';

interface SettingsStore {
  activeTab: SettingsTab;
  unsavedChanges: boolean;
  resetConfirmOpen: boolean;
  capturingShortcutFor: string | null;
  setActiveTab: (tab: SettingsTab) => void;
  setUnsavedChanges: (v: boolean) => void;
  setResetConfirmOpen: (v: boolean) => void;
  setCapturingShortcutFor: (action: string | null) => void;
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  activeTab: 'appearance',
  unsavedChanges: false,
  resetConfirmOpen: false,
  capturingShortcutFor: null,
  setActiveTab: (tab) => set({ activeTab: tab }),
  setUnsavedChanges: (v) => set({ unsavedChanges: v }),
  setResetConfirmOpen: (v) => set({ resetConfirmOpen: v }),
  setCapturingShortcutFor: (action) => set({ capturingShortcutFor: action }),
}));
