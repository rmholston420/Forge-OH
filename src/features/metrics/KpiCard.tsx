'use client';
import type { ReactNode } from 'react';

interface SparkPoint { value: number }

function Sparkline({ points }: { points: SparkPoint[] }) {
  if (points.length < 2) return null;
  const vals = points.map(p => p.value);
  const min  = Math.min(...vals);
  const max  = Math.max(...vals);
  const range = max - min || 1;
  const W = 64, H = 24;
  const xs = vals.map((_, i) => (i / (vals.length - 1)) * W);
  const ys = vals.map(v  => H - ((v - min) / range) * H);
  const d  = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  return (
    <svg width={W} height={H} aria-hidden="true" className="sparkline">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

interface KpiCardProps {
  label:      string;
  value:      ReactNode;
  delta?:     number | null;  // positive = up, negative = down
  sparkData?: SparkPoint[];
  unit?:      string;
}

export function KpiCard({ label, value, delta, sparkData, unit }: KpiCardProps) {
  const hasDelta = delta !== null && delta !== undefined;
  const up       = hasDelta && delta! > 0;
  const down     = hasDelta && delta! < 0;

  return (
    <div className="kpi-card">
      <p className="kpi-label">{label}</p>
      <div className="kpi-value-row">
        <span className="kpi-value tabular-nums">
          {value}{unit && <span className="kpi-unit">{unit}</span>}
        </span>
        {hasDelta && (
          <span
            className={`kpi-delta ${up ? 'kpi-delta--up' : down ? 'kpi-delta--down' : 'kpi-delta--flat'}`}
            aria-label={`${up ? 'Up' : down ? 'Down' : 'No change'} ${Math.abs(delta!).toFixed(1)}%`}
          >
            {up ? '↑' : down ? '↓' : '→'} {Math.abs(delta!).toFixed(1)}%
          </span>
        )}
      </div>
      {sparkData && sparkData.length >= 2 && (
        <div className="kpi-sparkline">
          <Sparkline points={sparkData} />
        </div>
      )}
    </div>
  );
}
