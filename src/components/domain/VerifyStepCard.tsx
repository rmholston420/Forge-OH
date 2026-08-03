'use client';
import React from 'react';
import type { TraceSpan } from '@/lib/schemas/trace';
import { VerificationStepSchema, type VerificationStep } from '@/lib/schemas/verify';
import styles from './VerifyStepCard.module.css';

/**
 * Renders one verify_step span as a card with iteration counter,
 * runner name, verdict badge, and truncated stdout/stderr tails.
 *
 * The card reads the ObservationEvent result out of `span.attributes`
 * (BFF pipes it through unchanged from the agent-server event stream).
 * The attribute keys mirror the Python VerificationStep field names —
 * see openhands_tools_ext/verify/schema.py.
 */
export interface VerifyStepCardProps {
  span: TraceSpan;
}

const VERDICT_LABEL: Record<VerificationStep['verdict'], string> = {
  pass: 'PASS',
  fail: 'FAIL',
  error: 'ERROR',
  skipped: 'SKIPPED',
};

const RUNNER_LABEL: Record<VerificationStep['runner'], string> = {
  pytest: 'pytest',
  vitest: 'vitest',
  jest: 'jest',
  npm_test: 'npm test',
  unknown: 'unknown',
};

/**
 * Attempt to parse a VerificationStep payload out of a span. The
 * ObservationEvent's `result` field can sit in either `result` or
 * `observation` in the BFF-normalized attributes dict, depending on the
 * agent-server version. Try both and give up cleanly.
 */
function extractVerifyStep(span: TraceSpan): VerificationStep | null {
  const attrs = span.attributes ?? {};
  const candidates: unknown[] = [
    attrs.result,
    attrs.observation,
    attrs.verify_step,
    attrs,  // last-resort: the span itself carries the fields
  ];
  for (const c of candidates) {
    const parsed = VerificationStepSchema.safeParse(c);
    if (parsed.success) return parsed.data;
  }
  return null;
}

export const VerifyStepCard: React.FC<VerifyStepCardProps> = ({ span }) => {
  const step = extractVerifyStep(span);
  if (!step) {
    return (
      <div className={styles.card} data-testid="verify-step-card-empty">
        <div className={styles.header}>
          <span className={styles.title}>Verify step</span>
          <span className={styles.iteration}>span attributes missing</span>
        </div>
      </div>
    );
  }

  const verdictClass = `${styles.verdictBadge} ${styles[`verdict--${step.verdict}`]}`;

  return (
    <div className={styles.card} data-testid="verify-step-card">
      <div className={styles.header}>
        <span className={styles.title}>Verify step</span>
        <span className={styles.iteration}>
          iteration {step.iteration} / {step.max_iterations}
        </span>
        <span className={verdictClass} data-verdict={step.verdict}>
          {VERDICT_LABEL[step.verdict]}
        </span>
      </div>

      <dl className={styles.details}>
        <div className={styles.detailRow}>
          <dt>Runner</dt>
          <dd>{RUNNER_LABEL[step.runner]}</dd>
        </div>
        <div className={styles.detailRow}>
          <dt>Command</dt>
          <dd>
            <code>{step.command || '—'}</code>
          </dd>
        </div>
        <div className={styles.detailRow}>
          <dt>Exit code</dt>
          <dd>{step.exit_code ?? '—'}</dd>
        </div>
        <div className={styles.detailRow}>
          <dt>Duration</dt>
          <dd>{step.duration_ms != null ? `${step.duration_ms.toFixed(0)}ms` : '—'}</dd>
        </div>
        <div className={styles.detailRow}>
          <dt>Targets</dt>
          <dd>
            {step.test_selected.length === 0 ? (
              '—'
            ) : (
              <ul className={styles.targets}>
                {step.test_selected.map((t) => (
                  <li key={t}>
                    <code>{t}</code>
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
        {step.files_edited_since_last_verify.length > 0 && (
          <div className={styles.detailRow}>
            <dt>Files edited</dt>
            <dd>
              <ul className={styles.targets}>
                {step.files_edited_since_last_verify.map((f) => (
                  <li key={f}>
                    <code>{f}</code>
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>

      {step.stdout_tail && (
        <details className={styles.tail}>
          <summary>stdout tail</summary>
          <pre className={styles.tailPre}>{step.stdout_tail}</pre>
        </details>
      )}
      {step.stderr_tail && (
        <details className={styles.tail}>
          <summary>stderr tail</summary>
          <pre className={styles.tailPre}>{step.stderr_tail}</pre>
        </details>
      )}
    </div>
  );
};

export default VerifyStepCard;
