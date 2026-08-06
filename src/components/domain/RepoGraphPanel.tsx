'use client';

/**
 * src/components/domain/RepoGraphPanel.tsx
 *
 * Slice D.5 — RepoGraph panel for the run detail Trace tab.
 *
 * Given a workspace path (typed by the user, or defaulted from the run),
 * indexes the workspace via POST /api/repograph/index and then shows:
 *   - a symbol search box (POST /api/repograph/search)
 *   - the callers / callees of the selected symbol
 *   - the git-history co-changed files for that symbol's file
 *
 * The panel is feature-flag-gated on FEATURE_REPOGRAPH; if disabled, it
 * renders a short explanation instead. It also queries /health so if
 * Neo4j is unreachable the user is told exactly why instead of getting a
 * silent empty state.
 */
import React, { useMemo, useState } from 'react';
import { useFeatureFlag } from '@/lib/feature-flags';
import { FEATURE_FLAGS } from '@/lib/feature-flags/flags';
import {
  useCallers,
  useCallees,
  useCoChanged,
  useFullGraph,
  useIndexWorkspace,
  useRepoGraphHealth,
  useSymbolSearch,
} from '@/features/repograph/hooks';
import type { RepoGraphSymbol } from '@/lib/schemas/repograph';
import { RepoGraphGraphView } from '@/features/repograph/RepoGraphGraphView';
import styles from './RepoGraphPanel.module.css';

type ViewMode = 'list' | 'graph';

export interface RepoGraphPanelProps {
  /** Optional workspace path prefilled in the "index" input. */
  defaultWorkspacePath?: string;
}

export const RepoGraphPanel: React.FC<RepoGraphPanelProps> = ({
  defaultWorkspacePath,
}) => {
  const { isEnabled } = useFeatureFlag();
  const enabled = isEnabled(FEATURE_FLAGS.REPOGRAPH);

  if (!enabled) {
    return (
      <section className={styles.panel} data-testid="repograph-panel-disabled">
        <header className={styles.header}>
          <h3 className={styles.title}>RepoGraph</h3>
          <span className={styles.status}>disabled</span>
        </header>
        <p className={styles.hint}>
          RepoGraph is disabled. Set{' '}
          <code>NEXT_PUBLIC_FEATURE_REPOGRAPH=true</code> and{' '}
          <code>REPOGRAPH_ENABLED=true</code> to enable structural
          repository-aware retrieval.
        </p>
      </section>
    );
  }

  return <RepoGraphPanelInner defaultWorkspacePath={defaultWorkspacePath} />;
};

// ---------------------------------------------------------------------------
// Inner (only mounted when the flag is on so we don't hit /health uselessly)
// ---------------------------------------------------------------------------

const RepoGraphPanelInner: React.FC<RepoGraphPanelProps> = ({
  defaultWorkspacePath,
}) => {
  const health = useRepoGraphHealth();
  const indexMut = useIndexWorkspace();

  const [workspaceInput, setWorkspaceInput] = useState(
    defaultWorkspacePath ?? '',
  );
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<RepoGraphSymbol | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('list');

  const repoKey = indexMut.data?.repo_key;
  const fullGraph = useFullGraph(repoKey, 500, viewMode === 'graph');
  const stats = indexMut.data?.stats;

  const search = useSymbolSearch(repoKey, query, Boolean(repoKey));
  const callers = useCallers(
    repoKey,
    selected?.name,
    selected?.rel_path,
    Boolean(selected),
  );
  const callees = useCallees(
    repoKey,
    selected?.rel_path,
    Boolean(selected),
  );
  const coChanged = useCoChanged(
    repoKey,
    selected?.rel_path,
    Boolean(selected),
  );

  const healthBadge = useMemo(() => {
    if (health.isLoading) return { text: 'checking…', ok: null as boolean | null };
    if (health.isError) return { text: 'unreachable', ok: false };
    const d = health.data;
    if (!d) return { text: 'unknown', ok: false };
    if (!d.enabled) return { text: 'BFF flag off', ok: false };
    if (!d.reachable)
      return { text: `neo4j down (${d.error ?? 'no detail'})`, ok: false };
    return {
      text: `neo4j ${d.neo4j_version ?? '?'} / ${d.database ?? '?'}`,
      ok: true,
    };
  }, [health]);

  function handleIndex(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!workspaceInput.trim()) return;
    indexMut.mutate({ workspacePath: workspaceInput.trim() });
    setSelected(null);
  }

  return (
    <section className={styles.panel} data-testid="repograph-panel">
      <header className={styles.header}>
        <h3 className={styles.title}>RepoGraph</h3>
        <span
          className={styles.status}
          data-ok={healthBadge.ok === null ? undefined : healthBadge.ok}
          title="Neo4j status"
        >
          {healthBadge.text}
        </span>
        {repoKey && (
          <div
            className={styles.viewToggle}
            role="group"
            aria-label="View mode"
            data-testid="repograph-view-toggle"
          >
            <button
              type="button"
              className={styles.viewToggleButton}
              data-selected={viewMode === 'list'}
              onClick={() => setViewMode('list')}
              aria-pressed={viewMode === 'list'}
            >
              List
            </button>
            <button
              type="button"
              className={styles.viewToggleButton}
              data-selected={viewMode === 'graph'}
              onClick={() => setViewMode('graph')}
              aria-pressed={viewMode === 'graph'}
              data-testid="repograph-toggle-graph"
            >
              Graph
            </button>
          </div>
        )}
      </header>

      <form className={styles.form} onSubmit={handleIndex}>
        <label className={styles.label} htmlFor="repograph-ws">
          Workspace path
        </label>
        <div className={styles.row}>
          <input
            id="repograph-ws"
            className={styles.input}
            type="text"
            value={workspaceInput}
            onChange={(e) => setWorkspaceInput(e.target.value)}
            placeholder="/home/rmholston/dev/forge-oh"
            spellCheck={false}
          />
          <button
            type="submit"
            className={styles.button}
            disabled={indexMut.isPending || healthBadge.ok !== true}
          >
            {indexMut.isPending ? 'indexing…' : 'Index'}
          </button>
        </div>
        {indexMut.isError && (
          <p className={styles.error}>
            index failed: {String(indexMut.error)}
          </p>
        )}
        {stats && (
          <p className={styles.stats} data-testid="repograph-stats">
            repo <code>{repoKey}</code> · files {stats.files} · symbols{' '}
            {stats.symbols} · calls {stats.calls} · methods{' '}
            {stats.method_edges}
          </p>
        )}
      </form>

      {repoKey && viewMode === 'graph' && (
        <div className={styles.results} data-testid="repograph-graph-container">
          {fullGraph.isFetching && (
            <p className={styles.hint}>loading graph…</p>
          )}
          {fullGraph.isError && (
            <p className={styles.error}>
              graph failed: {String(fullGraph.error)}
            </p>
          )}
          {fullGraph.data && (
            <>
              <p className={styles.stats}>
                {fullGraph.data.stats.files} files ·{' '}
                {fullGraph.data.stats.symbols} symbols ·{' '}
                {fullGraph.data.stats.edges} edges
              </p>
              <RepoGraphGraphView
                graph={fullGraph.data}
                onSelectSymbol={(s) =>
                  setSelected({
                    rel_path: s.rel_path,
                    name: s.name,
                    category: '',
                    start_line: s.start_line,
                    end_line: 0,
                    parent: null,
                    info: '',
                    pagerank: 0,
                  } as RepoGraphSymbol)
                }
              />
            </>
          )}
        </div>
      )}

      {repoKey && viewMode === 'list' && (
        <>
          <div className={styles.searchRow}>
            <input
              className={styles.input}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search symbols by name or file…"
              spellCheck={false}
              aria-label="Search symbols"
            />
          </div>

          <div className={styles.results}>
            {search.isFetching && (
              <p className={styles.hint}>searching…</p>
            )}
            {!search.isFetching && query && (search.data ?? []).length === 0 && (
              <p className={styles.hint}>No matches.</p>
            )}
            <ul className={styles.list}>
              {(search.data ?? []).map((sym) => (
                <li key={`${sym.rel_path}:${sym.name}:${sym.start_line}`} data-testid="repograph-search-result">
                  <button
                    className={styles.symbolButton}
                    data-selected={
                      selected?.rel_path === sym.rel_path &&
                      selected?.name === sym.name &&
                      selected?.start_line === sym.start_line
                    }
                    onClick={() => setSelected(sym)}
                  >
                    <span className={styles.symbolName}>{sym.name}</span>
                    <span className={styles.symbolMeta}>
                      {sym.category} · {sym.rel_path}:{sym.start_line}
                    </span>
                    <span className={styles.pagerank}>
                      pr {sym.pagerank.toFixed(3)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {selected && (
            <div className={styles.detail}>
              <h4 className={styles.subtitle}>
                {selected.name}{' '}
                <span className={styles.symbolMeta}>
                  ({selected.category} in {selected.rel_path}:
                  {selected.start_line})
                </span>
              </h4>
              <pre className={styles.signature}>{selected.info}</pre>

              <div className={styles.cols}>
                <ColumnList
                  title={`Callers of ${selected.name}`}
                  isLoading={callers.isLoading}
                  isError={callers.isError}
                  items={(callers.data ?? []).map((c) => ({
                    key: `${c.caller_file}:${c.call_line ?? ''}`,
                    primary: c.caller_file,
                    secondary: c.call_line
                      ? `line ${c.call_line}`
                      : undefined,
                  }))}
                  emptyText="No callers found in this repo."
                />

                <ColumnList
                  title={`Callees from ${selected.rel_path}`}
                  isLoading={callees.isLoading}
                  isError={callees.isError}
                  items={(callees.data ?? []).map((c) => ({
                    key: `${c.callee_file}:${c.callee}:${c.call_line ?? ''}`,
                    primary: c.callee,
                    secondary: `${c.callee_file} · pr ${c.pagerank.toFixed(3)}`,
                  }))}
                  emptyText="No outgoing calls tracked."
                />

                <ColumnList
                  title={`Co-changed with ${selected.rel_path}`}
                  isLoading={coChanged.isLoading}
                  isError={coChanged.isError}
                  items={
                    coChanged.data?.available
                      ? (coChanged.data.files ?? []).map((f) => ({
                          key: f.rel_path,
                          primary: f.rel_path,
                          secondary: `${f.commits} commit${f.commits === 1 ? '' : 's'}`,
                        }))
                      : []
                  }
                  emptyText={
                    coChanged.data && !coChanged.data.available
                      ? `git unavailable${coChanged.data.error ? ` (${coChanged.data.error})` : ''}`
                      : 'No git history detected.'
                  }
                />
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
};

// ---------------------------------------------------------------------------
// Small helper: labeled list column with loading + empty states.
// ---------------------------------------------------------------------------

interface ColumnListItem {
  key: string;
  primary: string;
  secondary?: string;
}

interface ColumnListProps {
  title: string;
  isLoading: boolean;
  isError: boolean;
  items: ColumnListItem[];
  emptyText: string;
}

const ColumnList: React.FC<ColumnListProps> = ({
  title,
  isLoading,
  isError,
  items,
  emptyText,
}) => (
  <div className={styles.col}>
    <div className={styles.colTitle}>{title}</div>
    {isLoading && <p className={styles.hint}>loading…</p>}
    {isError && <p className={styles.error}>query failed</p>}
    {!isLoading && !isError && items.length === 0 && (
      <p className={styles.hint}>{emptyText}</p>
    )}
    {!isLoading && !isError && items.length > 0 && (
      <ul className={styles.list}>
        {items.map((it) => (
          <li key={it.key} className={styles.listItem}>
            <span className={styles.symbolName}>{it.primary}</span>
            {it.secondary && (
              <span className={styles.symbolMeta}>{it.secondary}</span>
            )}
          </li>
        ))}
      </ul>
    )}
  </div>
);

export default RepoGraphPanel;
