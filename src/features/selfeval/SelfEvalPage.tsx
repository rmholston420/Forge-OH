'use client';

/**
 * `/selfeval` — cycle history + Run-now trigger.
 *
 * Layout:
 *   [Run-now button + status]
 *   [Cycle history table] --> each row links to /selfeval/[date]
 *
 * Zero cycles state falls back to a stub that just shows Run-now.
 */

import Link from 'next/link';
import type { Route } from 'next';

import { useCycles, useRunNow, useStatus } from './hooks';

function pctPassed(c: {
  tasks_passed: number;
  tasks_selected: number;
}): string {
  if (!c.tasks_selected) return '—';
  return `${((c.tasks_passed / c.tasks_selected) * 100).toFixed(0)}%`;
}

function dateFromFilename(fn: string): string {
  // 2026-08-03-selfeval.json or 2026-08-03-selfeval-2230.json
  return fn.slice(0, 10);
}

export default function SelfEvalPage() {
  const { data: cyclesData, isLoading: loadingCycles } = useCycles();
  const { data: status } = useStatus();
  const runNow = useRunNow();

  const running = Boolean(status?.running);
  const cycles = cyclesData?.cycles ?? [];

  return (
    <div className="selfeval-page">
      <div className="page-header">
        <h1>Self-Eval</h1>
        <button
          type="button"
          disabled={running || runNow.isPending}
          onClick={() => runNow.mutate()}
          className={`btn btn--primary ${running ? 'btn--disabled' : ''}`}
          aria-label="Run a self-eval cycle now"
        >
          {running ? 'Running…' : runNow.isPending ? 'Launching…' : 'Run now'}
        </button>
      </div>

      {status?.started_at && running && (
        <p className="text-muted" role="status">
          Cycle started at {new Date(status.started_at).toLocaleString()}
        </p>
      )}

      {runNow.isError && (
        <p role="alert" className="text-error">
          Failed to launch cycle: {(runNow.error as Error).message}
        </p>
      )}

      <h2>Cycle history</h2>
      {loadingCycles ? (
        <div className="skeleton" style={{ height: 120, borderRadius: 8 }} />
      ) : cycles.length === 0 ? (
        <p className="text-muted">
          No cycles yet. Hit <strong>Run now</strong> to fire the first one.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Selected</th>
              <th>Passed</th>
              <th>Failed</th>
              <th>Timed out</th>
              <th>Errored</th>
              <th>Pass rate</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((c) => {
              const date = dateFromFilename(c.filename);
              return (
                <tr key={c.filename}>
                  <td>{date}</td>
                  <td>{c.tasks_selected}</td>
                  <td>{c.tasks_passed}</td>
                  <td>{c.tasks_failed}</td>
                  <td>{c.tasks_timed_out}</td>
                  <td>{c.tasks_errored}</td>
                  <td>{pctPassed(c)}</td>
                  <td>
                    <Link href={`/selfeval/${date}` as Route}>Open →</Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
