'use client';

/**
 * src/components/domain/TrajectoryMemoryPanel.tsx
 *
 * Slice F.7 — Trajectory memory case-retrieval widget for the run
 * detail Overview tab.
 *
 * Given the current run's task_description (from RunSummary.taskPrompt),
 * this panel queries POST /api/trajectories/search and proactively
 * displays the top-k prior verified runs whose task + touched symbols
 * are closest to the current one. Each hit shows:
 *   - the prior task description
 *   - the final status (badge)
 *   - the co-ranked score (0.7 * semantic + 0.3 * symbol_overlap)
 *   - a short symptom line when present
 *   - the diff count / verify iteration count / repo key
 *
 * The panel is feature-flag-gated on FEATURE_TRAJECTORY_MEMORY.
 */
import React, { useMemo } from 'react';
import { useFeatureFlag } from '@/lib/feature-flags';
import { FEATURE_FLAGS } from '@/lib/feature-flags/flags';
import { useTrajectorySearch } from '@/features/trajectory-memory/hooks';
import {
  DEFAULT_RETRIEVAL_K,
  type TrajectoryRecord,
  type TrajectorySearchHit,
} from '@/lib/schemas/trajectory';
import styles from './TrajectoryMemoryPanel.module.css';

export interface TrajectoryMemoryPanelProps {
  /**
   * The current run's task description. When missing/empty the panel
   * renders an idle hint instead of hitting the network.
   */
  taskDescription: string | undefined;
  /** Optional current-run repo key to bias toward same-repo matches. */
  repoKey?: string;
  /**
   * Optional list of symbols the current run has already touched, used
   * to compute the symbol-overlap term in the co-ranked score.
   */
  currentSymbols?: string[];
  /** Exclude these run ids from the search (typically the current run). */
  excludeRunIds?: string[];
  /** Top-k budget. Defaults to DEFAULT_RETRIEVAL_K (3). */
  k?: number;
}

export const TrajectoryMemoryPanel: React.FC<TrajectoryMemoryPanelProps> = ({
  taskDescription,
  repoKey,
  currentSymbols,
  excludeRunIds,
  k = DEFAULT_RETRIEVAL_K,
}) => {
  const { isEnabled } = useFeatureFlag();
  const enabled = isEnabled(FEATURE_FLAGS.TRAJECTORY_MEMORY);

  if (!enabled) {
    return (
      <section
        className={styles.panel}
        data-testid="trajectory-memory-panel-disabled"
      >
        <header className={styles.header}>
          <h3 className={styles.title}>Prior similar runs</h3>
          <span className={styles.badge}>disabled</span>
        </header>
        <p className={styles.hint}>
          Trajectory memory is disabled. Set{' '}
          <code>NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY=true</code> to
          enable case-retrieval suggestions.
        </p>
      </section>
    );
  }

  return (
    <TrajectoryMemoryPanelInner
      taskDescription={taskDescription}
      repoKey={repoKey}
      currentSymbols={currentSymbols}
      excludeRunIds={excludeRunIds}
      k={k}
    />
  );
};

// ---------------------------------------------------------------------------
// Inner — only mounted when the flag is on
// ---------------------------------------------------------------------------

const TrajectoryMemoryPanelInner: React.FC<
  Required<Pick<TrajectoryMemoryPanelProps, 'k'>> &
    Omit<TrajectoryMemoryPanelProps, 'k'>
> = ({
  taskDescription,
  repoKey,
  currentSymbols,
  excludeRunIds,
  k,
}) => {
  const req = useMemo(() => {
    const task = (taskDescription ?? '').trim();
    if (!task) return undefined;
    return {
      task_description: task,
      k,
      verified_only: true,
      repo_key: repoKey || undefined,
      current_symbols: currentSymbols ?? [],
      exclude_run_ids: excludeRunIds ?? [],
    };
  }, [taskDescription, k, repoKey, currentSymbols, excludeRunIds]);

  const query = useTrajectorySearch(req);

  return (
    <section
      className={styles.panel}
      data-testid="trajectory-memory-panel"
      aria-label="Prior similar runs"
    >
      <header className={styles.header}>
        <h3 className={styles.title}>Prior similar runs</h3>
        <span className={styles.subtitle}>
          case-retrieval · top {k} · verified only
        </span>
        <div className={styles.spacer} />
        {query.isFetching && <span className={styles.badge}>loading…</span>}
      </header>

      {!req && (
        <p className={styles.hint} data-testid="trajectory-memory-idle">
          Waiting for a task description on this run.
        </p>
      )}

      {req && query.isError && (
        <p
          className={styles.error}
          role="alert"
          data-testid="trajectory-memory-error"
        >
          Could not load prior runs
          {query.error instanceof Error ? `: ${query.error.message}` : ''}.
        </p>
      )}

      {req && query.data && query.data.hits.length === 0 && (
        <p className={styles.hint} data-testid="trajectory-memory-empty">
          No matching prior runs yet. Completed runs on this workstation
          will populate this list.
        </p>
      )}

      {req && query.data && query.data.hits.length > 0 && (
        <ul className={styles.list} data-testid="trajectory-memory-hits">
          {query.data.hits.map((hit) => (
            <HitRow key={hit.record.trajectory_id} hit={hit} />
          ))}
        </ul>
      )}
    </section>
  );
};

// ---------------------------------------------------------------------------
// One retrieval hit
// ---------------------------------------------------------------------------

const HitRow: React.FC<{ hit: TrajectorySearchHit }> = ({ hit }) => {
  const { record, score, semantic_score, symbol_overlap } = hit;
  return (
    <li className={styles.hit} data-testid="trajectory-memory-hit">
      <div className={styles.hitHeader}>
        <span className={styles.hitTask} title={record.task_description}>
          {record.task_description || '(no task description)'}
        </span>
        <StatusPill record={record} />
      </div>

      <div className={styles.scoreRow} aria-label="retrieval scores">
        <span title="0.7 · semantic + 0.3 · symbol overlap">
          score {formatScore(score)}
        </span>
        <span title="cosine similarity of task embeddings">
          sem {formatScore(semantic_score)}
        </span>
        <span title="jaccard on repograph_symbols">
          sym {formatScore(symbol_overlap)}
        </span>
      </div>

      {record.symptom && (
        <p className={styles.symptom} title={record.symptom}>
          {record.symptom}
        </p>
      )}

      <div className={styles.meta}>
        <span title="files touched">{record.diffs.length} diffs</span>
        <span title="verify loop iterations">
          {record.verify_iterations.length} verify
        </span>
        {record.repograph_repo_key && (
          <span title="repograph repo key">
            repo {record.repograph_repo_key}
          </span>
        )}
        <span title="run id">{record.run_id}</span>
      </div>
    </li>
  );
};

const StatusPill: React.FC<{ record: TrajectoryRecord }> = ({ record }) => {
  const s = record.final_status;
  if (s === 'success') {
    return (
      <span className={styles.statusOk} data-testid="trajectory-status">
        success
      </span>
    );
  }
  if (s === 'failed' || s === 'verified_failure') {
    return (
      <span className={styles.statusFail} data-testid="trajectory-status">
        {s === 'verified_failure' ? 'verified failure' : 'failed'}
      </span>
    );
  }
  return (
    <span className={styles.statusOther} data-testid="trajectory-status">
      {s}
    </span>
  );
};

function formatScore(n: number): string {
  if (!Number.isFinite(n)) return '—';
  return n.toFixed(2);
}
