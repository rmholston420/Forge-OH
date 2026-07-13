/**
 * src/tests/unit/onboarding-store.test.ts
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useOnboardingStore } from '@/features/onboarding/store';

// Each test resets the store
beforeEach(() => useOnboardingStore.getState().reset());

describe('useOnboardingStore', () => {
  it('initial state: active=false, dismissed=false, currentStep=0', () => {
    const s = useOnboardingStore.getState();
    expect(s.active).toBe(false);
    expect(s.dismissed).toBe(false);
    expect(s.currentStep).toBe(0);
  });

  it('start() sets active=true', () => {
    useOnboardingStore.getState().start();
    expect(useOnboardingStore.getState().active).toBe(true);
  });

  it('start() after dismiss is a no-op (_onboardingDone guard)', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().dismiss();
    useOnboardingStore.getState().start();  // should no-op
    expect(useOnboardingStore.getState().active).toBe(false);
  });

  it('dismiss() sets active=false and dismissed=true', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().dismiss();
    const s = useOnboardingStore.getState();
    expect(s.active).toBe(false);
    expect(s.dismissed).toBe(true);
  });

  it('next() advances currentStep', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().next();
    expect(useOnboardingStore.getState().currentStep).toBe(1);
  });

  it('next() marks current step id as completed', () => {
    const { start, next, steps, completedIds } = useOnboardingStore.getState();
    start();
    const firstId = useOnboardingStore.getState().steps[0]?.id;
    next();
    expect(useOnboardingStore.getState().completedIds.has(firstId)).toBe(true);
  });

  it('next() on last step sets active=false and dismissed=true', () => {
    useOnboardingStore.getState().start();
    const { steps } = useOnboardingStore.getState();
    // Advance to last step
    for (let i = 0; i < steps.length; i++) {
      useOnboardingStore.getState().next();
    }
    const s = useOnboardingStore.getState();
    expect(s.active).toBe(false);
    expect(s.dismissed).toBe(true);
  });

  it('back() decrements currentStep', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().next();
    useOnboardingStore.getState().back();
    expect(useOnboardingStore.getState().currentStep).toBe(0);
  });

  it('back() at step 0 is a no-op', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().back();
    expect(useOnboardingStore.getState().currentStep).toBe(0);
  });

  it('markCompleted adds id to completedIds', () => {
    useOnboardingStore.getState().markCompleted('step-custom');
    expect(useOnboardingStore.getState().completedIds.has('step-custom')).toBe(true);
  });

  it('reset restores initial state and clears completedIds', () => {
    useOnboardingStore.getState().start();
    useOnboardingStore.getState().next();
    useOnboardingStore.getState().markCompleted('x');
    useOnboardingStore.getState().reset();
    const s = useOnboardingStore.getState();
    expect(s.active).toBe(false);
    expect(s.currentStep).toBe(0);
    expect(s.completedIds.size).toBe(0);
  });
});
