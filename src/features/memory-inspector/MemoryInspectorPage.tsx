'use client';
import React from 'react';
import { useRecentMemoryWrites } from './hooks';
import type { MemoryWriteRecord } from './schemas';
import { Banner } from '@/components/core/Banner';
import { EmptyState } from '@/components/core/EmptyState';
import { Skeleton } from '@/components/core/Skeleton';

const LIMIT = 50;

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function TierBadge({ tier }: { tier: string }) {
  return (
    <span
      aria-label={`PII tier ${tier}`}
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 4,
        background: 'var(--surface-2, #1f2937)',
        fontSize: 12,
      }}
    >
      {tier}
    </span>
  );
}

function Row({ r }: { r: MemoryWriteRecord }) {
  return (
    <tr>
      <td>{r.subject}</td>
      <td>{r.predicate}</td>
      <td>{r.object}</td>
      <td>{r.provenance}</td>
      <td>{r.confidence.toFixed(2)}</td>
      <td><TierBadge tier={r.piiTier} /></td>
      <td>{formatTime(r.writtenAt)}</td>
    </tr>
  );
}

export default function MemoryInspectorPage() {
  const { data, isLoading, error } = useRecentMemoryWrites(LIMIT);
  const isUnavailable =
    (error as (Error & { code?: string }) | null)?.code === 'MEMORY_UNAVAILABLE';

  return (
    <section aria-labelledby="memory-inspector-title">
      <header style={{ marginBottom: 16 }}>
        <h1 id="memory-inspector-title">Memory</h1>
        <p style={{ color: 'var(--text-muted, #94a3b8)', margin: 0 }}>
          Recent MemoryPort writes (newest first, up to {LIMIT}).
        </p>
      </header>

      {isUnavailable && (
        <Banner variant="warning" title="Memory service unavailable">
          Set NEO4J_PASSWORD and restart the BFF to enable the memory inspector.
        </Banner>
      )}

      {!isUnavailable && error && (
        <Banner variant="error" title="Failed to load memory writes">
          {(error as Error).message}
        </Banner>
      )}

      {isLoading && (
        <div aria-label="Loading memory writes">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      )}

      {!isLoading && !isUnavailable && !error && (data?.length ?? 0) === 0 && (
        <EmptyState
          title="No memory writes yet"
          description="MemoryPort writes will appear here as the agent curates them."
        />
      )}

      {!isLoading && (data?.length ?? 0) > 0 && (
        <table role="table" aria-label="Recent memory writes" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th scope="col">Subject</th>
              <th scope="col">Predicate</th>
              <th scope="col">Object</th>
              <th scope="col">Provenance</th>
              <th scope="col">Confidence</th>
              <th scope="col">PII tier</th>
              <th scope="col">Written</th>
            </tr>
          </thead>
          <tbody>
            {(data ?? []).map((r) => <Row key={r.id} r={r} />)}
          </tbody>
        </table>
      )}
    </section>
  );
}
