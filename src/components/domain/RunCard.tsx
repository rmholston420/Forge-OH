'use client';
import React from 'react';
import Link from 'next/link';
import type { Route } from 'next';
import { StatusBadge } from '@/components/core/Badge';
import type { RunSummary } from '@/lib/schemas/run';
import { formatDuration, formatCost, formatDate } from '@/lib/utils/format';
import styles from './RunCard.module.css';

export interface RunCardProps {
  run: RunSummary;
}

function formatSelectedModel(value?: string | null) {
  if (!value) return null;
  return value.replace(/^ollama\//, 'Ollama: ').replace(/^vllm\//, 'vLLM: ');
}

export const RunCard: React.FC<RunCardProps> = ({ run }) => {
  const selectedModelLabel = formatSelectedModel(run.selectedModel ?? run.routing?.selected ?? null);

  return (
    <Link href={`/runs/${run.id}` as Route} className={styles.card}>
      <div className={styles.main}>
        <div className={styles.titleRow}>
          <span className={styles.title}>{String(run.title ?? run.id)}</span>
          <StatusBadge status={run.status} />
        </div>
        <div className={styles.meta}>
          <span className={styles.chip}>
            <span aria-hidden="true">
              {run.workspaceType === 'docker' ? '📦' : run.workspaceType === 'remote_api' ? '🌐' : '💻'}
            </span>
            {String(run.workspaceType ?? 'local')}
          </span>
          <span className={styles.chip}>
            <span aria-hidden="true">🤖</span>
            {String(run.agentPresetName ?? 'Default')}
          </span>
          {selectedModelLabel && (
            <span className={styles.chip}>
              <span aria-hidden="true">🧠</span>
              {selectedModelLabel}
            </span>
          )}
          {Boolean(run.activeTool) && (
            <span className={styles.chipActive}>
              <span aria-hidden="true">⚡</span>
              {String(run.activeTool ?? '')}
            </span>
          )}
        </div>
      </div>
      <div className={styles.stats}>
        <span className={styles.stat}>{formatDuration(run.elapsedMs ?? null)}</span>
        <span className={styles.stat}>{formatCost(run.estimatedCostUsd ?? null)}</span>
        <span className={styles.statMeta}>{formatDate(String(run.updatedAt ?? new Date().toISOString()))}</span>
      </div>
    </Link>
  );
};
