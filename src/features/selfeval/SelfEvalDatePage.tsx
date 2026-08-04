'use client';

/**
 * `/selfeval/[date]` — one cycle's full outcome table + related proposals.
 *
 * Backend endpoint expects the exact summary filename, not the date, so we
 * derive the canonical filename from the URL segment. Multi-cycle days are
 * NOT supported at this MVP tier (spec says cycle filename can be
 * ``YYYY-MM-DD-selfeval-HHMM.json`` in that case; a follow-up ADR will pick
 * a UX for that when it actually happens).
 *
 * Chrome via SelfEval.module.css + core `Badge` component.
 */

import Link from 'next/link';
import type { Route } from 'next';

import { Badge, type BadgeVariant } from '@/components/core/Badge';

import type { TaskOutcome } from './api';
import { useCycle, useProposal, useProposals } from './hooks';

import styles from './SelfEval.module.css';

export interface SelfEvalDatePageProps {
  date: string; // YYYY-MM-DD
}

const VERDICT_VARIANT: Record<TaskOutcome['verdict'], BadgeVariant> = {
  passed: 'success',
  failed: 'error',
  timeout: 'warning',
  error: 'error',
};

function trajectoryDotClass(final: string | null | undefined): string {
  switch (final) {
    case 'agent-finished':
    case 'finished':
      return styles.trajectoryDotFinished;
    case 'timed_out':
    case 'timed-out':
      return styles.trajectoryDotTimedOut;
    case 'errored':
    case 'error':
      return styles.trajectoryDotErrored;
    default:
      return '';
  }
}

export default function SelfEvalDatePage({ date }: SelfEvalDatePageProps) {
  const summaryFilename = `${date}-selfeval.json`;
  const { data: cycle, isLoading, isError, error } = useCycle(summaryFilename);
  const { data: proposalsData } = useProposals(date);

  return (
    <div className={styles.datePage}>
      <div className={styles.header}>
        <h1>Cycle: {date}</h1>
        <Link href={'/selfeval' as Route} className={styles.backLink}>
          ← All cycles
        </Link>
      </div>

      {isLoading && (
        <div className="skeleton" style={{ height: 180, borderRadius: 8 }} />
      )}

      {isError && (
        <p role="alert" className={styles.errorBanner}>
          Could not load cycle: {(error as Error).message}
        </p>
      )}

      {cycle && (
        <>
          <div className={styles.kpiGrid}>
            <div className={styles.kpiCard}>
              <span className={styles.kpiLabel}>Passed</span>
              <span className={styles.kpiValue}>{cycle.tasks_passed}</span>
            </div>
            <div className={styles.kpiCard}>
              <span className={styles.kpiLabel}>Failed</span>
              <span className={styles.kpiValue}>{cycle.tasks_failed}</span>
            </div>
            <div className={styles.kpiCard}>
              <span className={styles.kpiLabel}>Timed out</span>
              <span className={styles.kpiValue}>{cycle.tasks_timed_out}</span>
            </div>
            <div className={styles.kpiCard}>
              <span className={styles.kpiLabel}>Errored</span>
              <span className={styles.kpiValue}>{cycle.tasks_errored}</span>
            </div>
          </div>

          <h2>Task outcomes</h2>
          <table className={styles.dataTable}>
            <thead>
              <tr>
                <th>Task</th>
                <th>Verdict</th>
                <th className={styles.numeric}>Duration</th>
                <th>Verify verdict</th>
                <th>Trajectory status</th>
                <th>Reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cycle.outcomes.map((o) => {
                const dotCls = trajectoryDotClass(o.trajectory_status);
                const hasRun = Boolean(o.run_id);
                return (
                  <tr key={`${o.task_id}-${o.run_id || 'no-run'}`}>
                    <td>
                      <code className={styles.taskId}>{o.task_id}</code>
                    </td>
                    <td>
                      <Badge variant={VERDICT_VARIANT[o.verdict]} size="sm">
                        {o.verdict}
                      </Badge>
                    </td>
                    <td className={`${styles.numeric} ${styles.mono}`}>
                      {Number.isFinite(o.duration_sec) ? `${o.duration_sec.toFixed(1)}s` : '—'}
                    </td>
                    <td className={styles.mono}>{o.verify_verdict ?? '—'}</td>
                    <td>
                      {o.trajectory_status ? (
                        <span className={styles.trajectoryStatus}>
                          <span
                            className={`${styles.trajectoryDot} ${dotCls}`}
                            aria-hidden="true"
                          />
                          {o.trajectory_status}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className={styles.reasonCell}>{o.failure_detail || '—'}</td>
                    <td>
                      {hasRun ? (
                        <Link href={`/runs/${o.run_id}` as Route} className={styles.rowLink}>
                          Trace →
                        </Link>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      <h2>Proposals</h2>
      {(proposalsData?.proposals ?? []).length === 0 ? (
        <p className={styles.emptyState}>No proposals recorded for {date}.</p>
      ) : (
        <ul className={styles.proposalList}>
          {proposalsData!.proposals.map((p) => (
            <li key={p.filename}>
              <ProposalCard filename={p.filename} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProposalCard({ filename }: { filename: string }) {
  const { data, isLoading } = useProposal(filename);
  return (
    <details className={styles.proposalCard}>
      <summary className={styles.proposalCardSummary}>{filename}</summary>
      {isLoading ? (
        <div className="skeleton" style={{ height: 60, marginTop: 8 }} />
      ) : data ? (
        <pre className={styles.proposalBody}>{data.body}</pre>
      ) : null}
    </details>
  );
}
