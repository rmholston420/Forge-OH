'use client';
import { useEffect } from 'react';
import { useOnboardingStore } from '@/features/onboarding/store';
import { OnboardingSpotlight } from './OnboardingSpotlight';
import { OnboardingTooltip   } from './OnboardingTooltip';

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const { active, dismissed, currentStep, steps, start } = useOnboardingStore();

  // Auto-start for first-time users
  useEffect(() => {
    if (!dismissed) {
      // Small delay so the DOM is painted before we measure targets
      const t = setTimeout(() => start(), 800);
      return () => clearTimeout(t);
    }
  }, [dismissed, start]);

  const step = steps[currentStep];

  return (
    <>
      {children}
      {active && step && (
        <>
          <OnboardingSpotlight targetSelector={step.targetSelector} />
          <OnboardingTooltip
            step={step}
            stepIndex={currentStep}
            totalSteps={steps.length}
          />
        </>
      )}
    </>
  );
}
