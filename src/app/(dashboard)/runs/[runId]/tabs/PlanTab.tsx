'use client';
import React from 'react';
import { useRunPlan } from '@/features/run-detail/plan-hooks';
import { Skeleton } from '@/components/core/Skeleton';
import { Banner } from '@/components/core/Banner';
import { EmptyState } from '@/components/core/EmptyState';

type Status = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

const STATUS_COLOR: Record<Status, string> = {
  pending:   '#64748b',
  running:   '#3b82f6',
  completed: '#10b981',
  failed:    '#ef4444',
  skipped:   '#a1a1aa',
};

const STATUS_ICON: Record<Status, string> = {
  pending:   '◯',
  running:   '◐',
  completed: '●',
  failed:    '✕',
  skipped:   '⊘',
};

export function PlanTab({ runId, isActive }: { runId: string; isActive: boolean }) {
  const { data: steps = [], isLoading, error } = useRunPlan(runId, isActive);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} width="100%" height={48} borderRadius="8px" />
        ))}
      </div>
    );
  }

  if (error) return <Banner variant="error">Failed to load plan.</Banner>;

  if (!steps.length) {
    return (
      <EmptyState
        title="No plan yet"
        description="The agent hasn't recorded any planning steps. task_tracker calls will show up here as the run progresses."
      />
    );
  }

  const sorted = [...steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  return (
    <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {sorted.map((s) => {
        const status = (s.status as Status) ?? 'pending';
        return (
          <li
            key={s.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid var(--border-subtle, #1f2937)',
              background: 'var(--surface-1, #0f172a)',
            }}
          >
            <span
              aria-label={status}
              style={{
                color: STATUS_COLOR[status],
                fontSize: 20,
                width: 24,
                textAlign: 'center',
                flexShrink: 0,
              }}
            >
              {STATUS_ICON[status]}
            </span>
            <span style={{ flex: 1, color: 'var(--text-primary, #e2e8f0)' }}>
              {s.title ?? s.label ?? s.id}
            </span>
            <span
              style={{
                color: STATUS_COLOR[status],
                fontSize: 12,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                flexShrink: 0,
              }}
            >
              {status}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export default PlanTab;
