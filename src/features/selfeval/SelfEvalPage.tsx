'use client';

/**
 * `/selfeval` — cycle history + Run-now trigger + live-cycle rail.
 *
 * Layout:
 *   [Header: h1 + Run-now button]
 *   [Live-cycle rail]     (only while status.running === true)
 *   [Finished notice]     (~10s after running -> false)
 *   [Cycle history table] --> each row links to /selfeval/[date]
 *
 * Zero-cycles falls back to an empty-state hint that just shows Run-now.
 * Uses SelfEval.module.css for all chrome; verdict badges use core `Badge`
 * and the run button uses core `Button` so classNames actually resolve
 * (raw string classNames on CSS-Module classes never match after hash).
 */

import Link from 'next/link';
import type { Route } from 'next';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/core/Button';

import type { CycleListItem, RunStatus } from './api';
import { useCycles, useRunNow, useStatus } from './hooks';

import styles from './SelfEval.module.css';

/* ── Helpers ────────────────────────────────────────────────── */

function pctPassed(c: CycleListItem): string {
  if (!c.tasks_selected) return '—';
  return `${((c.tasks_passed / c.tasks_selected) * 100).toFixed(0)}%`;
}

function dateFromFilename(fn: string): string {
  // 2026-08-03-selfeval.json or 2026-08-03-selfeval-2230.json
  return fn.slice(0, 10);
}

function formatHM(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function formatDuration(startIso: string | null, finishIso: string | null): string {
  if (!startIso || !finishIso) return '—';
  const start = Date.parse(startIso);
  const finish = Date.parse(finishIso);
  if (Number.isNaN(start) || Number.isNaN(finish) || finish < start) return '—';
  const secs = Math.round((finish - start) / 1000);
  if (secs < 60) return `${secs}s`;
  return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

function formatElapsed(startIso: string | null, nowMs: number): string {
  if (!startIso) return '';
  const start = Date.parse(startIso);
  if (Number.isNaN(start) || nowMs < start) return '';
  const secs = Math.floor((nowMs - start) / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/* ── Live-cycle rail ────────────────────────────────────────── */

function LiveCycleRail({ status }: { status: RunStatus }) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const elapsed = formatElapsed(status.started_at, nowMs);
  return (
    <div className={styles.liveRail} role="status" aria-live="polite">
      <span className={styles.liveRailDot} aria-hidden="true" />
      <span className={styles.liveRailLabel}>Cycle in progress</span>
      <span className={styles.liveRailMeta}>
        {status.started_at
          ? `started ${new Date(status.started_at).toLocaleTimeString()} · elapsed ${elapsed}`
          : ''}
      </span>
    </div>
  );
}

/* ── Cycle-finished one-shot notice ─────────────────────────── */

interface FinishedNoticeProps {
  cycle: CycleListItem | null;
  onDismiss: () => void;
}

function FinishedNotice({ cycle, onDismiss }: FinishedNoticeProps) {
  useEffect(() => {
    const id = window.setTimeout(onDismiss, 10_000);
    return () => window.clearTimeout(id);
  }, [onDismiss]);
  if (!cycle) return null;
  const failed = cycle.tasks_failed + cycle.tasks_errored + cycle.tasks_timed_out;
  const isFail = failed > 0;
  const cls = `${styles.finishedNotice} ${isFail ? styles.finishedNoticeFailed : ''}`;
  return (
    <div className={cls} role="status" aria-live="polite">
      <span>
        Cycle finished at {formatHM(cycle.finished_at)} — {cycle.tasks_passed} passed, {failed} failed
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className={styles.finishedNoticeDismiss}
        aria-label="Dismiss cycle-finished notice"
      >
        ✕
      </button>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────────── */

export default function SelfEvalPage() {
  const { data: cyclesData, isLoading: loadingCycles } = useCycles();
  const { data: status } = useStatus();
  const runNow = useRunNow();

  const running = Boolean(status?.running);
  const cycles = useMemo(() => cyclesData?.cycles ?? [], [cyclesData]);

  // Track running -> false transitions to trigger the finished notice.
  const prevRunning = useRef<boolean>(running);
  const [showFinished, setShowFinished] = useState(false);
  useEffect(() => {
    if (prevRunning.current && !running) setShowFinished(true);
    prevRunning.current = running;
  }, [running]);

  const latestCycle = cycles[0] ?? null;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>Self-Eval</h1>
        <Button
          variant="primary"
          disabled={running || runNow.isPending}
          onClick={() => runNow.mutate()}
          aria-label="Run a self-eval cycle now"
          loading={runNow.isPending}
        >
          {running ? 'Running…' : 'Run now'}
        </Button>
      </div>

      {running && status && <LiveCycleRail status={status} />}

      {showFinished && !running && (
        <FinishedNotice cycle={latestCycle} onDismiss={() => setShowFinished(false)} />
      )}

      {runNow.isError && (
        <p role="alert" className={styles.errorBanner}>
          Failed to launch cycle: {(runNow.error as Error).message}
        </p>
      )}

      <h2>Cycle history</h2>
      {loadingCycles ? (
        <div className="skeleton" style={{ height: 120, borderRadius: 8 }} />
      ) : cycles.length === 0 ? (
        <p className={styles.emptyState}>
          No cycles yet. Hit <strong>Run now</strong> to fire the first one.
        </p>
      ) : (
        <table className={styles.dataTable}>
          <thead>
            <tr>
              <th>Date</th>
              <th>Started</th>
              <th>Duration</th>
              <th className={styles.numeric}>Selected</th>
              <th className={styles.numeric}>Passed</th>
              <th className={styles.numeric}>Failed</th>
              <th className={styles.numeric}>Timed out</th>
              <th className={styles.numeric}>Errored</th>
              <th className={styles.numeric}>Pass rate</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((c) => {
              const date = dateFromFilename(c.filename);
              return (
                <tr key={c.filename}>
                  <td>{date}</td>
                  <td className={styles.mono} title={c.started_at ?? undefined}>
                    {formatHM(c.started_at)}
                  </td>
                  <td className={styles.mono}>{formatDuration(c.started_at, c.finished_at)}</td>
                  <td className={styles.numeric}>{c.tasks_selected}</td>
                  <td className={styles.numeric}>{c.tasks_passed}</td>
                  <td className={styles.numeric}>{c.tasks_failed}</td>
                  <td className={styles.numeric}>{c.tasks_timed_out}</td>
                  <td className={styles.numeric}>{c.tasks_errored}</td>
                  <td className={styles.numeric}>{pctPassed(c)}</td>
                  <td>
                    <Link href={`/selfeval/${date}` as Route} className={styles.rowLink}>
                      Open →
                    </Link>
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
