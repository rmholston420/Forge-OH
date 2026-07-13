import { create } from 'zustand';
import type { ArtifactType } from '@/lib/schemas/artifact';

interface ArtifactsStore {
  typeFilter: ArtifactType | 'all';
  previewId: string | null;
  setTypeFilter: (t: ArtifactType | 'all') => void;
  setPreviewId: (id: string | null) => void;
}

export const useArtifactsStore = create<ArtifactsStore>((set) => ({
  typeFilter: 'all',
  previewId: null,
  setTypeFilter: (typeFilter) => set({ typeFilter }),
  setPreviewId: (previewId) => set({ previewId }),
}));
