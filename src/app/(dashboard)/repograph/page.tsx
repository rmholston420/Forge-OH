'use client';

/**
 * src/app/(dashboard)/repograph/page.tsx
 *
 * Stage 4.3 — standalone RepoGraph explorer. Wraps the existing
 * RepoGraphPanel with a workspace-path prefill drawn from either a
 * ?ws=... query param or a sensible default (~/dev/forge-oh).
 *
 * Feature-gated on FEATURE_REPOGRAPH via the panel itself.
 */
import React from 'react';
import { useSearchParams } from 'next/navigation';
import { RepoGraphPanel } from '@/components/domain/RepoGraphPanel';

export default function RepoGraphPage() {
  const search = useSearchParams();
  const ws = search.get('ws') ?? '/home/rmholston/dev/forge-oh';

  return (
    <main
      data-testid="repograph-page"
      style={{ padding: 'var(--space-4, 1rem)', maxWidth: 1400, margin: '0 auto' }}
    >
      <h1
        style={{
          margin: '0 0 var(--space-3, 12px)',
          fontSize: 'var(--font-size-heading, 1.4rem)',
          color: 'var(--color-text-primary)',
        }}
      >
        RepoGraph
      </h1>
      <RepoGraphPanel defaultWorkspacePath={ws} />
    </main>
  );
}
