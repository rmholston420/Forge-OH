'use client';

/**
 * src/app/(dashboard)/repograph/page.tsx
 *
 * Stage 4.3 — standalone RepoGraph explorer. Wraps the existing
 * RepoGraphPanel with a workspace-path prefill drawn from either a
 * ?ws=... query param or a sensible default (~/dev/forge-oh).
 *
 * `useSearchParams()` must be rendered under a Suspense boundary in
 * Next.js 15+ so the outer route can prerender; the inner component
 * that actually reads the params lives in a Suspense subtree.
 *
 * Feature-gated on FEATURE_REPOGRAPH via the panel itself.
 */
import React, { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { RepoGraphPanel } from '@/components/domain/RepoGraphPanel';

const DEFAULT_WS = '/home/rmholston/dev/forge-oh';

function RepoGraphPanelWithSearchParams() {
  const search = useSearchParams();
  const ws = search?.get('ws') ?? DEFAULT_WS;
  return <RepoGraphPanel defaultWorkspacePath={ws} />;
}

export default function RepoGraphPage() {
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
      <Suspense fallback={<RepoGraphPanel defaultWorkspacePath={DEFAULT_WS} />}>
        <RepoGraphPanelWithSearchParams />
      </Suspense>
    </main>
  );
}
