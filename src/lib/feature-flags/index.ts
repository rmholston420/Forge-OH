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
 *
 * IMPORTANT: Next.js inlines NEXT_PUBLIC_* env vars into client bundles only
 * when accessed as a *literal* property (e.g. `process.env.NEXT_PUBLIC_FOO`).
 * A computed access like `process.env[key]` where `key` is a template string
 * stays `undefined` in the browser after tree-shaking. That's why we build a
 * static map here with one literal read per flag. Adding a new flag requires
 * a new line below.
 */
const STATIC_FLAG_VALUES: Record<FeatureFlag, string | undefined> = {
  // Phase 0
  LIVE_STREAM: process.env.NEXT_PUBLIC_FEATURE_LIVE_STREAM,
  // Phase 1 — Run Command Centre
  RUN_LIST: process.env.NEXT_PUBLIC_FEATURE_RUN_LIST,
  RUN_DETAIL_SHELL: process.env.NEXT_PUBLIC_FEATURE_RUN_DETAIL_SHELL,
  PLAN_RAIL: process.env.NEXT_PUBLIC_FEATURE_PLAN_RAIL,
  EVENT_TIMELINE: process.env.NEXT_PUBLIC_FEATURE_EVENT_TIMELINE,
  APPROVAL_GATE: process.env.NEXT_PUBLIC_FEATURE_APPROVAL_GATE,
  // Phase 2 — Artifact & Code Intelligence
  ARTIFACT_VIEWER: process.env.NEXT_PUBLIC_FEATURE_ARTIFACT_VIEWER,
  TERMINAL_PANE: process.env.NEXT_PUBLIC_FEATURE_TERMINAL_PANE,
  BROWSER_PANE: process.env.NEXT_PUBLIC_FEATURE_BROWSER_PANE,
  METRICS_PANE: process.env.NEXT_PUBLIC_FEATURE_METRICS_PANE,
  // Phase 3 — Configuration Hub
  WORKSPACE_MANAGER: process.env.NEXT_PUBLIC_FEATURE_WORKSPACE_MANAGER,
  AGENT_PRESETS: process.env.NEXT_PUBLIC_FEATURE_AGENT_PRESETS,
  MCP_PANEL: process.env.NEXT_PUBLIC_FEATURE_MCP_PANEL,
  SECRETS_VAULT: process.env.NEXT_PUBLIC_FEATURE_SECRETS_VAULT,
  // Phase 4 — Observability Suite
  OBSERVABILITY_OVERVIEW: process.env.NEXT_PUBLIC_FEATURE_OBSERVABILITY_OVERVIEW,
  LOOP_GUARD_MONITOR: process.env.NEXT_PUBLIC_FEATURE_LOOP_GUARD_MONITOR,
  TRACE_VIEWER: process.env.NEXT_PUBLIC_FEATURE_TRACE_VIEWER,
  // Phase 5 — Plugin & Extension Layer
  PLUGIN_MARKETPLACE: process.env.NEXT_PUBLIC_FEATURE_PLUGIN_MARKETPLACE,
  RUN_REPLAY: process.env.NEXT_PUBLIC_FEATURE_RUN_REPLAY,
  RIGPA_LMS: process.env.NEXT_PUBLIC_FEATURE_RIGPA_LMS,
  // Recommendation #1 — RepoGraph
  REPOGRAPH: process.env.NEXT_PUBLIC_FEATURE_REPOGRAPH,
  // Recommendation #3 — Trajectory memory
  TRAJECTORY_MEMORY: process.env.NEXT_PUBLIC_FEATURE_TRAJECTORY_MEMORY,
};

function readEnvFlag(flag: FeatureFlag): string | undefined {
  // In Node/test environments, prefer a live read from process.env so that
  // tests which mutate process.env at runtime see the change. In the
  // browser bundle, `process.env[key]` with a template key returns
  // undefined (Next.js inlines only literal accesses), so we fall back to
  // the static map compiled at build time.
  const key = `NEXT_PUBLIC_FEATURE_${flag}`;
  if (typeof process !== 'undefined' && process.env && key in process.env) {
    const live = process.env[key];
    if (live !== undefined) return live;
  }
  return STATIC_FLAG_VALUES[flag];
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
