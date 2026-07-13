/**
 * onboarding-schemas.test.ts
 *
 * The existing onboarding-store.test.ts tests the Zustand store behaviour.
 * This file covers the OnboardingStepSchema and DEFAULT_TOUR_STEPS constant
 * which have no test coverage anywhere.
 */
import { describe, it, expect } from 'vitest';
import { OnboardingStepSchema, DEFAULT_TOUR_STEPS } from '@/lib/schemas/onboarding';

const VALID_STEP = {
  id: 'sidebar',
  title: 'Navigate',
  description: 'Use the sidebar.',
  targetSelector: '[data-tour="sidebar"]',
};

describe('OnboardingStepSchema', () => {
  it('parses a valid step with defaults applied', () => {
    const result = OnboardingStepSchema.parse(VALID_STEP);
    expect(result.completed).toBe(false);
    expect(result.skippable).toBe(true);
  });

  it('overrides defaults when explicitly provided', () => {
    const result = OnboardingStepSchema.parse({
      ...VALID_STEP,
      completed: true,
      skippable: false,
    });
    expect(result.completed).toBe(true);
    expect(result.skippable).toBe(false);
  });

  it('requires id, title, description, and targetSelector', () => {
    expect(() => OnboardingStepSchema.parse({})).toThrow();
    expect(() => OnboardingStepSchema.parse({ id: 's' })).toThrow();
  });
});

describe('DEFAULT_TOUR_STEPS', () => {
  it('contains exactly 7 steps', () => {
    expect(DEFAULT_TOUR_STEPS).toHaveLength(7);
  });

  it('every step has a unique id', () => {
    const ids = DEFAULT_TOUR_STEPS.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('every step passes schema validation', () => {
    for (const step of DEFAULT_TOUR_STEPS) {
      expect(() => OnboardingStepSchema.parse(step)).not.toThrow();
    }
  });

  it('all steps start with completed: false', () => {
    expect(DEFAULT_TOUR_STEPS.every((s) => s.completed === false)).toBe(true);
  });

  it('all steps have a non-empty targetSelector', () => {
    expect(DEFAULT_TOUR_STEPS.every((s) => s.targetSelector.length > 0)).toBe(true);
  });

  it('includes the sidebar step', () => {
    expect(DEFAULT_TOUR_STEPS.find((s) => s.id === 'sidebar')).toBeDefined();
  });

  it('includes the approval-banner step', () => {
    expect(DEFAULT_TOUR_STEPS.find((s) => s.id === 'approval-banner')).toBeDefined();
  });
});
