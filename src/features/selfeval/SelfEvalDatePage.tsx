'use client';

/**
 * `/selfeval/[date]` — one cycle's full outcome table + related proposals.
 *
 * Backend endpoint expects the exact summary filename, not the date, so we
 * derive the canonical filename from the URL segment. Multi-cycle days are
 * NOT supported at this MVP tier (spec says cycle filename can be
 * ``YYYY-MM-DD-selfeval-HHMM.json`` in that case; a follow-up ADR will pick
 * a UX for that when it actually happens).
 */

import Link from 'next/link';
import type { Route } from 'next';

import { useCycle, useProposal, useProposals } from './hooks';

export interface SelfEvalDatePageProps {
  date: string; // YYYY-MM-DD
}

const VERDICT_STYLE: Record<string, string> = {
  passed: 'badge badge--success',
  failed: 'badge badge--error',
  timeout: 'badge badge--warning',
  error: 'badge badge--error',
};

export default function SelfEvalDatePage({ date }: SelfEvalDatePageProps) {
  const summaryFilename = `${date}-selfeval.json`;
  const { data: cycle, isLoading, isError, error } = useCycle(summaryFilename);
  const { data: proposalsData } = useProposals(date);

  return (
    <div className="selfeval-date-page">
      <div className="page-header">
        <h1>Cycle: {date}</h1>
        <Link href={'/selfeval' as Route} className="text-muted">
          ← All cycles
        </Link>
      </div>

      {isLoading && (
        <div className="skeleton" style={{ height: 180, borderRadius: 8 }} />
      )}

      {isError && (
        <p role="alert" className="text-error">
          Could not load cycle: {(error as Error).message}
        </p>
      )}

      {cycle && (
        <>
          <div className="kpi-grid" style={{ marginBottom: 16 }}>
            <div className="kpi">
              <span className="kpi-label">Passed</span>
              <span className="kpi-value">{cycle.tasks_passed}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">Failed</span>
              <span className="kpi-value">{cycle.tasks_failed}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">Timed out</span>
              <span className="kpi-value">{cycle.tasks_timed_out}</span>
            </div>
            <div className="kpi">
              <span className="kpi-label">Errored</span>
              <span className="kpi-value">{cycle.tasks_errored}</span>
            </div>
          </div>

          <h2>Task outcomes</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Verdict</th>
                <th>Duration</th>
                <th>Verify verdict</th>
                <th>Trajectory status</th>
                <th>Reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cycle.outcomes.map((o) => (
                <tr key={`${o.task_id}-${o.run_id ?? 'no-run'}`}>
                  <td>{o.task_id}</td>
                  <td>
                    <span className={VERDICT_STYLE[o.verdict] ?? 'badge'}>
                      {o.verdict}
                    </span>
                  </td>
                  <td>{o.duration_sec != null ? `${o.duration_sec.toFixed(1)}s` : '—'}</td>
                  <td>{o.verify_verdict ?? '—'}</td>
                  <td>{o.final_status ?? '—'}</td>
                  <td className="text-muted" style={{ maxWidth: 320 }}>
                    {o.reason ?? '—'}
                  </td>
                  <td>
                    {o.run_id ? (
                      <Link href={`/runs/${o.run_id}` as Route}>Trace →</Link>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h2 style={{ marginTop: 32 }}>Proposals</h2>
      {(proposalsData?.proposals ?? []).length === 0 ? (
        <p className="text-muted">No proposals for this date.</p>
      ) : (
        <ul className="proposal-list" style={{ listStyle: 'none', padding: 0 }}>
          {proposalsData!.proposals.map((p) => (
            <li key={p.filename} style={{ marginBottom: 24 }}>
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
    <details className="card">
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{filename}</summary>
      {isLoading ? (
        <div className="skeleton" style={{ height: 60, marginTop: 8 }} />
      ) : data ? (
        <pre
          style={{
            whiteSpace: 'pre-wrap',
            fontFamily: 'inherit',
            marginTop: 8,
          }}
        >
          {data.body}
        </pre>
      ) : null}
    </details>
  );
}
