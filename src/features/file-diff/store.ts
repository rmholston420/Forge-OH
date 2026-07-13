import { create } from 'zustand';

interface FileDiffStore {
  selectedPath: string | null;
  diffMode: 'split' | 'unified';
  setSelectedPath: (path: string | null) => void;
  setDiffMode: (mode: 'split' | 'unified') => void;
}

export const useFileDiffStore = create<FileDiffStore>((set) => ({
  selectedPath: null,
  diffMode: 'split',
  setSelectedPath: (path) => set({ selectedPath: path }),
  setDiffMode: (mode) => set({ diffMode: mode }),
}));
