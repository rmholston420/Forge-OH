'use client';
import { useMetricsSummary, useDailyMetrics, useModelBreakdown, useWorkspaceBreakdown } from './hooks';
import { useMetricsStore } from './store';
import { KpiCard } from './KpiCard';
import { formatDuration, formatCost } from '@/lib/utils/format';
import type { Period } from './schemas';

const PERIODS: { label: string; value: Period }[] = [
  { label: 'Last 7 days',  value: '7d'  },
  { label: 'Last 30 days', value: '30d' },
  { label: 'Last 90 days', value: '90d' },
  { label: 'All time',     value: 'all' },
];

export default function MetricsDashboardPage() {
  const { period, setPeriod } = useMetricsStore();
  const { data: summary,    isLoading: loadS } = useMetricsSummary(period);
  const { data: daily = [],  isLoading: loadD } = useDailyMetrics(period);
  const { data: models = [],             } = useModelBreakdown(period);
  const { data: workspaces = [],         } = useWorkspaceBreakdown(period);

  return (
    <div className="metrics-page">
      <div className="page-header">
        <h1>Metrics</h1>
        <div className="filter-tabs" role="tablist" aria-label="Time period">
          {PERIODS.map(p => (
            <button key={p.value} role="tab"
              aria-selected={period === p.value}
              className={`filter-tab ${period === p.value ? 'filter-tab--active' : ''}`}
              onClick={() => setPeriod(p.value)}
            >{p.label}</button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      <div className="kpi-grid">
        {loadS ? (
          [1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 96, borderRadius: 8 }} />)
        ) : summary ? (
          <>
            <KpiCard label="Total runs"   value={summary.totalRuns}
              delta={summary.deltaRuns}
              sparkData={daily.slice(-7).map((d: any) => ({ value: d.runs }))} />
            <KpiCard label="Total cost"   value={formatCost(summary.totalCostUsd)}
              delta={summary.deltaCostUsd}
              sparkData={daily.slice(-7).map((d: any) => ({ value: d.costUsd }))} />
            <KpiCard label="Success rate" value={`${(summary.successRate * 100).toFixed(1)}`} unit="%"
              delta={null} />
            <KpiCard label="Avg duration" value={formatDuration(summary.avgDurationMs)}
              delta={null} />
          </>
        ) : null}
      </div>

      {/* Daily chart placeholder — Chart.js loaded dynamically */}
      <div className="metrics-chart-section">
        <h2>Runs &amp; Cost over time</h2>
        {loadD ? (
          <div className="skeleton" style={{ height: 240, borderRadius: 8 }} />
        ) : daily.length === 0 ? (
          <div className="empty-state">
            <p>No run data for this period.</p>
          </div>
        ) : (
          <div className="chart-wrapper" aria-label="Daily runs and cost chart">
            {/* CostLineChart rendered via dynamic import in real app */}
            <pre className="chart-data-debug" style={{ display: 'none' }}>
              {JSON.stringify(daily, null, 2)}
            </pre>
            <p className="chart-loading-note text-muted">
              Chart.js renders here — {daily.length} data points loaded.
            </p>
          </div>
        )}
      </div>

      {/* Model breakdown + Workspace table */}
      <div className="metrics-bottom-grid">
        <section aria-label="Model breakdown">
          <h2>By model</h2>
          {models.length === 0 ? (
            <p className="text-muted">No model data.</p>
          ) : (
            <table className="metrics-table">
              <thead><tr>
                <th>Model</th><th>Runs</th><th>Cost</th><th>Tokens</th>
              </tr></thead>
              <tbody>
                {models.map((m: any) => (
                  <tr key={m.model}>
                    <td>{m.model}</td>
                    <td className="tabular-nums">{m.runs}</td>
                    <td className="tabular-nums">{formatCost(m.costUsd)}</td>
                    <td className="tabular-nums">{m.tokens.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section aria-label="Workspace breakdown">
          <h2>By workspace</h2>
          {workspaces.length === 0 ? (
            <p className="text-muted">No workspace data.</p>
          ) : (
            <table className="metrics-table">
              <thead><tr>
                <th>Workspace</th><th>Runs</th><th>Cost</th>
              </tr></thead>
              <tbody>
                {workspaces.map((w: any) => (
                  <tr key={w.workspaceId}>
                    <td><a href={`/workspaces`}>{w.name}</a></td>
                    <td className="tabular-nums">{w.runs}</td>
                    <td className="tabular-nums">{formatCost(w.costUsd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
