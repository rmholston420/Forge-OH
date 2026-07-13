import { create } from 'zustand';

interface BrowserStore {
  selectedFrameId: string | null;
  isPlaying: boolean;
  playheadIndex: number;
  setSelectedFrame: (id: string | null) => void;
  setPlaying: (v: boolean) => void;
  setPlayheadIndex: (i: number) => void;
}

export const useBrowserStore = create<BrowserStore>((set) => ({
  selectedFrameId: null,
  isPlaying: false,
  playheadIndex: 0,
  setSelectedFrame: (selectedFrameId) => set({ selectedFrameId }),
  setPlaying: (isPlaying) => set({ isPlaying }),
  setPlayheadIndex: (playheadIndex) => set({ playheadIndex }),
}));
