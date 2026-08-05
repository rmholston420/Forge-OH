'use client';

// App Router error boundary for the (dashboard) segment.
//
// Purpose: contain client-component throws so they cannot cascade into a
// Next.js Fast-Refresh re-render loop that saturates every CPU core.
// See DEBUG_LOG 2026-08-05 (agent-presets envelope drift caused
// next-server to peg at 1900% CPU because the throw kept re-rendering
// under Fast Refresh).
//
// This is defense-in-depth. Individual bugs (bad envelope handling,
// undefined.slice(), etc.) should still be fixed at their source — but
// this boundary guarantees that when one slips through, the developer
// sees a fallback card, not a melted workstation.

import { useEffect } from 'react';

interface DashboardErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function DashboardError({ error, reset }: DashboardErrorProps) {
  useEffect(() => {
    // Surface in dev tools console for easy inspection.
    // eslint-disable-next-line no-console
    console.error('[dashboard-error-boundary]', error);
  }, [error]);

  return (
    <div
      style={{
        padding: '2rem',
        margin: '1rem',
        border: '1px solid var(--color-border-danger, #7a1f1f)',
        borderRadius: 8,
        background: 'var(--color-surface-danger, rgba(122, 31, 31, 0.08))',
        color: 'var(--color-text-primary, inherit)',
      }}
      role="alert"
      aria-live="assertive"
    >
      <h2 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1.25rem' }}>
        Dashboard page crashed
      </h2>
      <p style={{ marginBottom: '1rem' }}>
        A client component threw an error rendering this page. The error boundary
        caught it before it could pin the dev server in a Fast-Refresh loop.
      </p>
      <details style={{ marginBottom: '1rem' }}>
        <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>Error detail</summary>
        <pre
          style={{
            padding: '0.75rem',
            background: 'var(--color-surface-2, rgba(0, 0, 0, 0.25))',
            borderRadius: 4,
            overflow: 'auto',
            fontSize: '0.8rem',
            lineHeight: 1.4,
          }}
        >
          {error.message}
          {error.digest ? `\n\nDigest: ${error.digest}` : ''}
          {error.stack ? `\n\n${error.stack}` : ''}
        </pre>
      </details>
      <button
        type="button"
        onClick={reset}
        className="btn btn-primary"
        style={{
          padding: '0.5rem 1rem',
          borderRadius: 4,
          cursor: 'pointer',
          background: 'var(--color-accent-primary, #3b82f6)',
          color: 'white',
          border: 'none',
        }}
      >
        Retry
      </button>
    </div>
  );
}
