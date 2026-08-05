'use client';

// Root-level App Router error boundary.
//
// Catches errors that escape the (dashboard)/error.tsx segment boundary —
// most commonly, errors thrown in root layout, providers, or any layout
// above the (dashboard) segment. Must render its own <html> and <body>
// because it replaces the RootLayout entirely.
//
// See DEBUG_LOG 2026-08-05 for the root cause this boundary is defending
// against: client-component throws + Next.js dev + Fast Refresh = every
// CPU core saturated in a re-render loop.

import { useEffect } from 'react';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error('[global-error-boundary]', error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          padding: '2rem',
          fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif',
          background: '#0d1117',
          color: '#e6edf3',
          minHeight: '100vh',
        }}
      >
        <div
          style={{
            maxWidth: 720,
            margin: '4rem auto',
            padding: '2rem',
            border: '1px solid #7a1f1f',
            borderRadius: 8,
            background: 'rgba(122, 31, 31, 0.08)',
          }}
          role="alert"
          aria-live="assertive"
        >
          <h1 style={{ marginTop: 0, fontSize: '1.5rem' }}>Forge-OH crashed at the root</h1>
          <p>
            An error escaped every downstream error boundary. This should be rare —
            it usually means a root layout, provider, or middleware threw during
            initial render.
          </p>
          <details style={{ marginBottom: '1rem' }}>
            <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>Error detail</summary>
            <pre
              style={{
                padding: '0.75rem',
                background: 'rgba(0, 0, 0, 0.35)',
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
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 4,
              cursor: 'pointer',
              background: '#3b82f6',
              color: 'white',
              border: 'none',
              fontSize: '1rem',
            }}
          >
            Reload dashboard
          </button>
        </div>
      </body>
    </html>
  );
}
