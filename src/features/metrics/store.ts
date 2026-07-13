import { create } from 'zustand';
import type { Period } from './schemas';

interface MetricsStore {
  period: Period;
  setPeriod: (p: Period) => void;
}

export const useMetricsStore = create<MetricsStore>((set) => ({
  period: '30d',
  setPeriod: (p) => set({ period: p }),
}));
