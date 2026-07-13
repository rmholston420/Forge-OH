'use client';
import { useEffect } from 'react';
import { useOnboardingStore } from '@/features/onboarding/store';
import type { OnboardingStep } from '@/lib/schemas/onboarding';

interface Props {
  step:       OnboardingStep;
  stepIndex:  number;
  totalSteps: number;
}

export function OnboardingTooltip({ step, stepIndex, totalSteps }: Props) {
  const { next, back, dismiss } = useOnboardingStore();
  const isFirst = stepIndex === 0;
  const isLast  = stepIndex === totalSteps - 1;

  // Keyboard nav
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft')  back();
      if (e.key === 'Escape')     dismiss();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next, back, dismiss]);

  return (
    <div
      className="onboarding-tooltip"
      role="dialog"
      aria-modal="false"
      aria-label={`Tour step ${stepIndex + 1} of ${totalSteps}: ${step.title}`}
      aria-live="polite"
      style={{ zIndex: 9999 }}
    >
      <div className="onboarding-tooltip-header">
        <span className="onboarding-step-count">
          {stepIndex + 1} / {totalSteps}
        </span>
        {step.skippable && (
          <button type="button" className="btn-link" onClick={dismiss}
            aria-label="Skip tour">
            Skip tour
          </button>
        )}
      </div>

      <h3 className="onboarding-tooltip-title">{step.title}</h3>
      <p  className="onboarding-tooltip-desc">{step.description}</p>

      <div className="onboarding-tooltip-actions">
        {!isFirst && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={back}>
            ← Back
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={next}
          autoFocus
        >
          {isLast ? 'Finish' : 'Next →'}
        </button>
      </div>
    </div>
  );
}
