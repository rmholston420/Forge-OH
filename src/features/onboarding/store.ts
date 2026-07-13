import { create } from 'zustand';
import { DEFAULT_TOUR_STEPS } from '@/lib/schemas/onboarding';
import type { OnboardingStep } from '@/lib/schemas/onboarding';

interface OnboardingStore {
  active:       boolean;
  dismissed:    boolean;
  currentStep:  number;
  steps:        OnboardingStep[];
  completedIds: Set<string>;
  start:        () => void;
  dismiss:      () => void;
  next:         () => void;
  back:         () => void;
  markCompleted:(id: string) => void;
  reset:        () => void;
}

// In-memory flag (no localStorage — sandbox safe)
let _onboardingDone = false;

export const useOnboardingStore = create<OnboardingStore>((set, get) => ({
  active:       false,
  dismissed:    false,
  currentStep:  0,
  steps:        DEFAULT_TOUR_STEPS,
  completedIds: new Set(),

  start: () => {
    if (_onboardingDone) return;
    set({ active: true, currentStep: 0 });
  },

  dismiss: () => {
    _onboardingDone = true;
    set({ active: false, dismissed: true });
  },

  next: () => {
    const { currentStep, steps, markCompleted } = get();
    markCompleted(steps[currentStep]?.id);
    if (currentStep >= steps.length - 1) {
      _onboardingDone = true;
      set({ active: false, dismissed: true });
    } else {
      set({ currentStep: currentStep + 1 });
    }
  },

  back: () => {
    const { currentStep } = get();
    if (currentStep > 0) set({ currentStep: currentStep - 1 });
  },

  markCompleted: (id: string) => {
    set((s) => ({ completedIds: new Set([...s.completedIds, id]) }));
  },

  reset: () => {
    _onboardingDone = false;
    set({ active: false, dismissed: false, currentStep: 0, completedIds: new Set() });
  },
}));
