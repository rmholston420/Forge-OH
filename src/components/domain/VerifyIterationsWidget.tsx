'use client';
import React from 'react';
import type { TraceSpan } from '@/lib/schemas/trace';
import { VerificationStepSchema, type VerificationStep } from '@/lib/schemas/verify';
import styles from './VerifyIterationsWidget.module.css';

/**
 * Metrics-tab widget: "verify iterations per task".
 *
 * Since verify_step events already flow through the trace stream, we
 * compute stats client-side from `spans` rather than adding a new BFF
 * endpoint. Two derived numbers:
 *
 *   - **iterations used** — max of `iteration` across all verify spans in
 *     this run (the retry counter's high-water mark).
 *   - **last verdict** — the verdict from the highest-iteration span.
 *
 * Plus a horizontal chip strip showing the sequence of verdicts.
 */
export interface VerifyIterationsWidgetProps {
  spans: TraceSpan[];
}

function extractStep(span: TraceSpan): VerificationStep | null {
  const attrs = span.attributes ?? {};
  for (const c of [attrs.result, attrs.observation, attrs.verify_step, attrs]) {
    const parsed = VerificationStepSchema.safeParse(c);
    if (parsed.success) return parsed.data;
  }
  return null;
}

export const VerifyIterationsWidget: React.FC<VerifyIterationsWidgetProps> = ({ spans }) => {
  const verifySteps = spans
    .filter((s) => s.kind === 'verify')
    .map(extractStep)
    .filter((s): s is VerificationStep => s !== null)
    .sort((a, b) => a.iteration - b.iteration);

  if (verifySteps.length === 0) {
    return (
      <div className={styles.card} data-testid="verify-iterations-empty">
        <div className={styles.header}>Verify iterations</div>
        <div className={styles.emptyBody}>No verify steps in this run.</div>
      </div>
    );
  }

  const latest = verifySteps[verifySteps.length - 1];
  const maxIter = Math.max(...verifySteps.map((s) => s.max_iterations));
  const usedIter = Math.max(...verifySteps.map((s) => s.iteration));

  return (
    <div className={styles.card} data-testid="verify-iterations">
      <div className={styles.header}>Verify iterations</div>
      <div className={styles.big}>
        {usedIter}
        <span className={styles.bigSlash}> / {maxIter}</span>
      </div>
      <div className={styles.subline}>
        last verdict:{' '}
        <span className={`${styles.verdict} ${styles[`verdict--${latest.verdict}`]}`}>
          {latest.verdict}
        </span>
      </div>
      <div className={styles.chipRow} aria-label="Verdict history">
        {verifySteps.map((s) => (
          <span
            key={s.iteration}
            className={`${styles.chip} ${styles[`chip--${s.verdict}`]}`}
            title={`iteration ${s.iteration}: ${s.verdict}`}
          >
            {s.iteration}
          </span>
        ))}
      </div>
    </div>
  );
};

export default VerifyIterationsWidget;
