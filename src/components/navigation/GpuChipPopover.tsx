'use client';

/**
 * GpuChipPopover — 300 s sparkline for a single GPU metric.
 *
 * Consumes `/api/gpu/history?window_sec=300` (bounded by the BFF's
 * `FORGE_GPU_HISTORY_SEC` ring, default 900 s). Refreshes every 2 s
 * while open. Rendered via `createPortal` so it isn't clipped by the
 * Topbar's `overflow: hidden`.
 *
 * Accessibility:
 *   - Escape closes.
 *   - Outside click closes.
 *   - `role="dialog"` + `aria-label` describes the metric.
 */

import React from 'react';
import { createPortal } from 'react-dom';
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import styles from './GpuChipPopover.module.css';
import { bffFetch } from '@/lib/http/bff-client';

export type MetricKey = 'temperature_c' | 'utilization_pct' | 'vram_pct' | 'power_w';

interface HistorySample {
  ts_epoch: number;
  temperature_c: number | null;
  utilization_pct: number | null;
  memory_used_mib: number | null;
  memory_total_mib: number | null;
  power_w: number | null;
}

interface HistoryPayload {
  window_sec: number | null;
  cutoff_c: number;
  gpus: Record<string, HistorySample[]>;
}

interface Thresholds {
  warn?: number;
  cutoff?: number | null;
  critical?: number | null;
}

interface Props {
  metric: MetricKey;
  anchorRect: DOMRect | null;
  onClose: () => void;
  thresholds: Thresholds;
  label: string;
  unit: string;
}

const WINDOW_SEC = 300;
const POLL_MS = 2_000;

const METRIC_LABEL: Record<MetricKey, string> = {
  temperature_c: 'Temperature',
  utilization_pct: 'GPU Utilization',
  vram_pct: 'VRAM Used',
  power_w: 'Power Draw',
};

function deriveValue(s: HistorySample, key: MetricKey): number | null {
  if (key === 'vram_pct') {
    if (s.memory_used_mib == null || s.memory_total_mib == null || s.memory_total_mib === 0) {
      return null;
    }
    return (s.memory_used_mib / s.memory_total_mib) * 100;
  }
  const v = s[key];
  return typeof v === 'number' ? v : null;
}

interface Point {
  t: number; // seconds relative to now (negative = past)
  v: number;
}

export const GpuChipPopover: React.FC<Props> = ({
  metric,
  anchorRect,
  onClose,
  thresholds,
  label,
  unit,
}) => {
  const [points, setPoints] = React.useState<Point[]>([]);
  const [loading, setLoading] = React.useState(true);
  const popoverRef = React.useRef<HTMLDivElement | null>(null);

  // Fetch loop
  React.useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const res = await bffFetch(`/api/gpu/history?window_sec=${WINDOW_SEC}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as HistoryPayload;
        const now = Date.now() / 1000;
        // Fold multi-GPU into a peak-of-samples-at-nearest-timestamp.
        // In practice this app is single-GPU; the fold degenerates to
        // "just take gpu 0" for single-GPU boxes.
        const gpuKeys = Object.keys(data.gpus);
        const merged: Point[] = [];
        if (gpuKeys.length === 1) {
          for (const s of data.gpus[gpuKeys[0]]) {
            const v = deriveValue(s, metric);
            if (v !== null) merged.push({ t: s.ts_epoch - now, v });
          }
        } else if (gpuKeys.length > 1) {
          // Peak across GPUs at each sample index — history is aligned.
          const arrays = gpuKeys.map((k) => data.gpus[k]);
          const minLen = Math.min(...arrays.map((a) => a.length));
          for (let i = 0; i < minLen; i++) {
            let peak: number | null = null;
            let ts = 0;
            for (const arr of arrays) {
              const s = arr[i];
              const v = deriveValue(s, metric);
              if (v !== null && (peak === null || v > peak)) {
                peak = v;
                ts = s.ts_epoch;
              }
            }
            if (peak !== null) merged.push({ t: ts - now, v: peak });
          }
        }
        if (!cancelled) {
          setPoints(merged);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      } finally {
        if (!cancelled) {
          timer = setTimeout(tick, POLL_MS);
        }
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [metric]);

  // Escape + outside click close
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    const onClick = (e: MouseEvent) => {
      const el = popoverRef.current;
      if (el && !el.contains(e.target as Node)) onClose();
    };
    window.addEventListener('keydown', onKey);
    // Defer outside-click listener by one tick so the click that
    // opened the popover doesn't immediately close it.
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', onClick);
    }, 0);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
      clearTimeout(timer);
    };
  }, [onClose]);

  if (!anchorRect) return null;

  // Position popover under the chip. Right-align to the anchor's
  // right edge so it never clips the viewport on the topbar.
  const style: React.CSSProperties = {
    position: 'fixed',
    top: Math.round(anchorRect.bottom + 6),
    right: Math.max(8, Math.round(window.innerWidth - anchorRect.right)),
    zIndex: 1000,
  };

  const values = points.map((p) => p.v);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  const cur = values.length ? values[values.length - 1] : null;

  // Y domain: pad by ~10% so the line doesn't touch the border.
  // For percentages, clamp to 0–100.
  const isPct = metric === 'utilization_pct' || metric === 'vram_pct';
  const rawLo = Math.min(min, thresholds.warn ?? Infinity) - (max - min) * 0.1;
  const rawHi = Math.max(max, thresholds.critical ?? -Infinity) + (max - min) * 0.1;
  const yLo = isPct ? Math.max(0, Math.floor(rawLo)) : Math.floor(rawLo);
  const yHi = isPct
    ? Math.min(100, Math.ceil(rawHi))
    : Math.ceil(rawHi);

  const body = (
    <div
      ref={popoverRef}
      className={styles.popover}
      style={style}
      role="dialog"
      aria-label={`${METRIC_LABEL[metric]} — last ${WINDOW_SEC / 60} minutes`}
    >
      <div className={styles.header}>
        <span className={styles.title}>{METRIC_LABEL[metric]}</span>
        <span className={styles.window}>{WINDOW_SEC / 60} min</span>
      </div>
      <div className={styles.stats}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>now</span>
          <span className={styles.statValue}>
            {cur !== null ? `${cur.toFixed(0)}${unit}` : '—'}
          </span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>min</span>
          <span className={styles.statValue}>
            {values.length ? `${min.toFixed(0)}${unit}` : '—'}
          </span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>max</span>
          <span className={styles.statValue}>
            {values.length ? `${max.toFixed(0)}${unit}` : '—'}
          </span>
        </div>
      </div>
      <div className={styles.chart}>
        {loading && points.length === 0 ? (
          <div className={styles.loading}>loading…</div>
        ) : points.length === 0 ? (
          <div className={styles.loading}>no data</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
              <XAxis dataKey="t" hide domain={[-WINDOW_SEC, 0]} type="number" />
              <YAxis hide domain={[yLo, yHi]} type="number" />
              {thresholds.warn !== undefined && (
                <ReferenceLine
                  y={thresholds.warn}
                  stroke="var(--color-status-warn, #d99a00)"
                  strokeDasharray="2 3"
                  strokeOpacity={0.6}
                />
              )}
              {thresholds.critical != null && (
                <ReferenceLine
                  y={thresholds.critical}
                  stroke="var(--color-status-crit, #c93a3a)"
                  strokeDasharray="2 3"
                  strokeOpacity={0.6}
                />
              )}
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface-2, #1a1d24)',
                  border: '1px solid var(--color-border-subtle, #2a2f3a)',
                  fontSize: 11,
                  padding: '4px 8px',
                }}
                labelFormatter={(t) => `${Math.abs(Number(t)).toFixed(0)} s ago`}
                formatter={(v) => {
                  const n = typeof v === 'number' ? v : Number(v);
                  return [Number.isFinite(n) ? `${n.toFixed(0)}${unit}` : '—', label];
                }}
              />
              <Line
                type="monotone"
                dataKey="v"
                stroke="var(--color-accent-primary, #7aa2f7)"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );

  return typeof document !== 'undefined' ? createPortal(body, document.body) : null;
};
