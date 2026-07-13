/**
 * src/lib/feature-flags/index.ts
 *
 * Feature flag runtime helpers.
 *
 * Server Components (Node.js):
 *   isFeatureEnabled('RUN_LIST')  → reads process.env directly
 *
 * Client Components (browser):
 *   useFeatureFlag('RUN_LIST')    → React hook, reads NEXT_PUBLIC_ env vars
 *   OR: isFeatureEnabled() also works in client bundles via NEXT_PUBLIC_ prefix
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § Definition of Done
 */

'use client';

import { useCallback } from 'react';
import { FEATURE_FLAGS } from './flags';
import type { FeatureFlag } from './flags';

export { FEATURE_FLAGS } from './flags';
export type { FeatureFlag } from './flags';

// ---------------------------------------------------------------------------
// Env var resolution
// ---------------------------------------------------------------------------

/**
 * Read the env var for a feature flag.
 * Works in both server (process.env) and client (NEXT_PUBLIC_FEATURE_*) contexts.
 */
function readEnvFlag(flag: FeatureFlag): string | undefined {
  const key = `NEXT_PUBLIC_FEATURE_${flag}`;
  // Next.js replaces NEXT_PUBLIC_ vars at build time for client bundles.
  // On the server, process.env is always available.
  if (typeof process !== 'undefined' && process.env) {
    return process.env[key];
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// isFeatureEnabled — universal (server + client)
// ---------------------------------------------------------------------------

/**
 * Returns true if the feature flag is enabled.
 *
 * A flag is considered enabled when the corresponding env var is the
 * string ``"true"`` (case-insensitive).  All other values (including
 * absent / undefined) resolve to disabled.
 *
 * @example
 * if (isFeatureEnabled('RUN_LIST')) {
 *   // render run list feature
 * }
 */
export function isFeatureEnabled(flag: FeatureFlag): boolean {
  return readEnvFlag(flag)?.toLowerCase() === 'true';
}

// ---------------------------------------------------------------------------
// requireFeatureFlag — server-side guard rail
// ---------------------------------------------------------------------------

/**
 * Asserts a feature flag is enabled.  Throws an Error if not.
 * Use in Next.js Server Components or route handlers to hard-gate
 * server-side rendering of a feature.
 *
 * @throws {Error} If the flag is not enabled.
 */
export function requireFeatureFlag(flag: FeatureFlag): void {
  if (!isFeatureEnabled(flag)) {
    throw new Error(
      `Feature "${flag}" is disabled. ` +
        `Set NEXT_PUBLIC_FEATURE_${flag}=true to enable it.`,
    );
  }
}

// ---------------------------------------------------------------------------
// useFeatureFlag — React hook for Client Components
// ---------------------------------------------------------------------------

/**
 * React hook that returns a stable callback to check feature flags.
 * Suitable for use in Client Components.
 *
 * @example
 * const { isEnabled } = useFeatureFlag();
 * if (isEnabled('RUN_LIST')) { ... }
 */
export function useFeatureFlag(): { isEnabled: (flag: FeatureFlag) => boolean } {
  const isEnabled = useCallback((flag: FeatureFlag) => isFeatureEnabled(flag), []);
  return { isEnabled };
}

// ---------------------------------------------------------------------------
// getAllFlags — diagnostic helper
// ---------------------------------------------------------------------------

/**
 * Returns the resolved state of every feature flag.
 * Useful for the Observability debug panel.
 */
export function getAllFlags(): Record<FeatureFlag, boolean> {
  return Object.fromEntries(
    Object.values(FEATURE_FLAGS).map((flag) => [flag, isFeatureEnabled(flag)]),
  ) as Record<FeatureFlag, boolean>;
}
