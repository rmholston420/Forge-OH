import { create } from 'zustand';

interface TerminalStore {
  inputEnabled: boolean;
  pendingInput: string;
  setInputEnabled: (v: boolean) => void;
  setPendingInput: (v: string) => void;
}

export const useTerminalStore = create<TerminalStore>((set) => ({
  inputEnabled: false,
  pendingInput: '',
  setInputEnabled: (v) => set({ inputEnabled: v }),
  setPendingInput: (v) => set({ pendingInput: v }),
}));
