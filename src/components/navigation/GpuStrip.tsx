'use client';

/**
 * GpuStrip — always-visible GPU health widget for the top bar.
 *
 * Polls `GET /api/gpu` every 2 s (matches BFF poller cadence in
 * `bff/services/gpu_monitor.py`) and renders three color-coded chips:
 * temperature, utilization, VRAM %. Power is shown as a subdued
 * suffix. Each chip becomes red when its cutoff is reached; the
 * temperature chip additionally uses the snapshot's `warn_c` and
 * `critical_c` bands (52 C / 88 C for RTX 5090) for a yellow
 * midband.
 *
 * Clicking a chip opens a 300 s sparkline popover (GpuChipPopover)
 * anchored to that chip. When `available === false` or the fetch
 * itself fails, we render a single grey "GPU n/a" chip instead of
 * throwing.
 */

import React from 'react';
import styles from './GpuStrip.module.css';
import { bffFetch } from '@/lib/http/bff-client';
import { GpuChipPopover, type MetricKey } from './GpuChipPopover';

interface GpuSample {
  index: number;
  name?: string | null;
  temperature_c?: number | null;
  utilization_pct?: number | null;
  memory_used_mib?: number | null;
  memory_total_mib?: number | null;
  power_w?: number | null;
}

interface GpuSnapshot {
  available: boolean;
  cutoff_c: number;
  warn_c: number;
  critical_c: number;
  vram_cutoff_pct: number | null;
  util_cutoff_pct: number | null;
  power_cutoff_w: number | null;
  gpus: GpuSample[];
  peaks: {
    temperature_c: number | null;
    utilization_pct: number | null;
    vram_pct: number | null;
    power_w: number | null;
  };
}

type Level = 'ok' | 'warn' | 'crit' | 'muted';

const POLL_MS = 2_000;
// Fallback thresholds when the snapshot doesn't supply a cutoff. Kept
// deliberately conservative — a "warn" chip is a nudge, not an alarm.
const VRAM_WARN_PCT = 85;
const UTIL_WARN_PCT = 90;

function classifyTemp(
  t: number,
  warn: number,
  cutoff: number,
  critical: number,
): Level {
  if (t >= Math.min(cutoff, critical)) return 'crit';
  if (t >= warn) return 'warn';
  return 'ok';
}

function classifyPct(
  v: number,
  cutoff: number | null,
  fallbackWarn: number,
): Level {
  if (cutoff !== null && v >= cutoff) return 'crit';
  if (v >= fallbackWarn) return 'warn';
  return 'ok';
}

function classifyPower(v: number, cutoff: number | null): Level {
  if (cutoff !== null && v >= cutoff) return 'crit';
  if (cutoff !== null && v >= cutoff * 0.9) return 'warn';
  return 'ok';
}

function fmt(v: number | null | undefined, digits = 0): string {
  return typeof v === 'number' ? v.toFixed(digits) : '\u2014';
}

interface ChipProps {
  metric: MetricKey;
  label?: string;
  value: number | null | undefined;
  unit: string;
  level: Level;
  extraClass?: string;
  onOpen: (metric: MetricKey, rect: DOMRect) => void;
  activeMetric: MetricKey | null;
}

const Chip: React.FC<ChipProps> = ({
  metric,
  label,
  value,
  unit,
  level,
  extraClass,
  onOpen,
  activeMetric,
}) => {
  const ref = React.useRef<HTMLButtonElement | null>(null);
  const cls = [styles.chip, styles[level], extraClass].filter(Boolean).join(' ');
  return (
    <button
      ref={ref}
      type="button"
      className={cls}
      aria-haspopup="dialog"
      aria-expanded={activeMetric === metric}
      aria-label={`Open ${metric} history`}
      onClick={() => {
        if (ref.current) onOpen(metric, ref.current.getBoundingClientRect());
      }}
    >
      {label ? <span className={styles.label}>{label}</span> : null}
      <span className={styles.value}>{fmt(value, 0)}</span>
      <span className={styles.unit}>{unit}</span>
    </button>
  );
};

export const GpuStrip: React.FC = () => {
  const [snap, setSnap] = React.useState<GpuSnapshot | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [activeMetric, setActiveMetric] = React.useState<MetricKey | null>(null);
  const [anchorRect, setAnchorRect] = React.useState<DOMRect | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      try {
        const res = await bffFetch('/api/gpu');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as GpuSnapshot;
        if (!cancelled) {
          setSnap(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'error');
        }
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
  }, []);

  const handleOpen = (metric: MetricKey, rect: DOMRect) => {
    setActiveMetric((cur) => (cur === metric ? null : metric));
    setAnchorRect(rect);
  };
  const handleClose = () => setActiveMetric(null);

  if (error || !snap || !snap.available) {
    return (
      <div className={styles.strip} role="status" aria-label="GPU status">
        <span
          className={`${styles.chip} ${styles.muted}`}
          title={error ?? 'GPU telemetry unavailable'}
        >
          GPU n/a
        </span>
      </div>
    );
  }

  const { peaks } = snap;
  const tempLevel: Level =
    peaks.temperature_c === null
      ? 'muted'
      : classifyTemp(
          peaks.temperature_c,
          snap.warn_c,
          snap.cutoff_c,
          snap.critical_c,
        );
  const utilLevel: Level =
    peaks.utilization_pct === null
      ? 'muted'
      : classifyPct(peaks.utilization_pct, snap.util_cutoff_pct, UTIL_WARN_PCT);
  const vramLevel: Level =
    peaks.vram_pct === null
      ? 'muted'
      : classifyPct(peaks.vram_pct, snap.vram_cutoff_pct, VRAM_WARN_PCT);
  const powerLevel: Level =
    peaks.power_w === null
      ? 'muted'
      : classifyPower(peaks.power_w, snap.power_cutoff_w);

  // Title text — full detail on hover, including cutoffs.
  const gpuName = snap.gpus[0]?.name ?? 'GPU';
  const title = [
    gpuName,
    `temp ${fmt(peaks.temperature_c, 0)} C (warn ${snap.warn_c}, cutoff ${snap.cutoff_c}, critical ${snap.critical_c})`,
    `util ${fmt(peaks.utilization_pct, 0)}%` +
      (snap.util_cutoff_pct !== null ? ` (cutoff ${snap.util_cutoff_pct}%)` : ''),
    `vram ${fmt(peaks.vram_pct, 0)}%` +
      (snap.vram_cutoff_pct !== null ? ` (cutoff ${snap.vram_cutoff_pct}%)` : ''),
    `power ${fmt(peaks.power_w, 0)} W` +
      (snap.power_cutoff_w !== null ? ` (cutoff ${snap.power_cutoff_w} W)` : ''),
  ].join('\n');

  // Threshold config per metric for the popover's reference lines.
  const thresholdsFor = (m: MetricKey) => {
    switch (m) {
      case 'temperature_c':
        return {
          warn: snap.warn_c,
          cutoff: snap.cutoff_c,
          critical: Math.min(snap.cutoff_c, snap.critical_c),
        };
      case 'utilization_pct':
        return { warn: UTIL_WARN_PCT, critical: snap.util_cutoff_pct };
      case 'vram_pct':
        return { warn: VRAM_WARN_PCT, critical: snap.vram_cutoff_pct };
      case 'power_w':
        return {
          warn: snap.power_cutoff_w !== null ? snap.power_cutoff_w * 0.9 : undefined,
          critical: snap.power_cutoff_w,
        };
    }
  };

  const unitFor = (m: MetricKey): string => {
    switch (m) {
      case 'temperature_c':
        return '°C';
      case 'utilization_pct':
      case 'vram_pct':
        return '%';
      case 'power_w':
        return ' W';
    }
  };

  return (
    <>
      <div className={styles.strip} role="status" aria-label="GPU health" title={title}>
        <Chip
          metric="temperature_c"
          label="T"
          value={peaks.temperature_c}
          unit="C"
          level={tempLevel}
          onOpen={handleOpen}
          activeMetric={activeMetric}
        />
        <Chip
          metric="utilization_pct"
          label="U"
          value={peaks.utilization_pct}
          unit="%"
          level={utilLevel}
          onOpen={handleOpen}
          activeMetric={activeMetric}
        />
        <Chip
          metric="vram_pct"
          label="V"
          value={peaks.vram_pct}
          unit="%"
          level={vramLevel}
          onOpen={handleOpen}
          activeMetric={activeMetric}
        />
        <Chip
          metric="power_w"
          value={peaks.power_w}
          unit="W"
          level={powerLevel}
          extraClass={styles.power}
          onOpen={handleOpen}
          activeMetric={activeMetric}
        />
      </div>
      {activeMetric && (
        <GpuChipPopover
          metric={activeMetric}
          anchorRect={anchorRect}
          onClose={handleClose}
          thresholds={thresholdsFor(activeMetric)}
          label={activeMetric}
          unit={unitFor(activeMetric)}
        />
      )}
    </>
  );
};
