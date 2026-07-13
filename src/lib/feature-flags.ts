/**
 * src/lib/feature-flags.ts
 *
 * Feature flag system for Forge-OH vertical slices.
 *
 * SPEC REQUIREMENT (Definition of Done, every slice):
 *   "Feature flag gating FEATURE_[SLICE_NAME]_ENABLED"
 *
 * Usage:
 *   if (isFeatureEnabled('RUNS_HOME')) { ... }
 *
 * Environment variable pattern (set in .env.local or deployment env):
 *   NEXT_PUBLIC_FEATURE_RUNS_HOME_ENABLED=true
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § Slice 5D
 */

// ---------------------------------------------------------------------------
// Slice flag keys — one per vertical slice, ordered by execution order
// ---------------------------------------------------------------------------

export type SliceFlag =
  // Phase 0
  | 'FOUNDATIONS'
  // Phase 1 — Run Supervision MVP
  | 'RUNS_HOME'
  | 'RUN_DETAIL'
  | 'PLAN_RAIL'
  // Phase 2 — Code, Terminal, Artifacts
  | 'FILE_DIFFS'
  | 'TERMINAL'
  | 'ARTIFACTS'
  // Phase 3 — Environment, Integrations, Governance
  | 'WORKSPACES'
  | 'MCP_PLUGINS'
  | 'SECRETS'
  // Phase 4 — Browser, Observability, Tracing
  | 'BROWSER'
  | 'OBSERVABILITY'
  | 'TRACE_EXPLORER'
  // Phase 5 — Refinement, Safety, Rigpa-LMS
  | 'APPROVALS'
  | 'FORK_COMPARE'
  | 'RIGPA_LMS'
  | 'BUILD_HARDENING'
  | 'MODEL_ROUTER';

// ---------------------------------------------------------------------------
// Default values — Phase 0 foundations always on; all slices default OFF
// ---------------------------------------------------------------------------

export const FEATURE_DEFAULTS: Record<SliceFlag, boolean> = {
  FOUNDATIONS: true,     // Phase 0 is always on — it IS the shell
  RUNS_HOME: false,
  RUN_DETAIL: false,
  PLAN_RAIL: false,
  FILE_DIFFS: false,
  TERMINAL: false,
  ARTIFACTS: false,
  WORKSPACES: false,
  MCP_PLUGINS: false,
  SECRETS: false,
  BROWSER: false,
  OBSERVABILITY: false,
  TRACE_EXPLORER: false,
  APPROVALS: false,
  FORK_COMPARE: false,
  RIGPA_LMS: false,
  BUILD_HARDENING: false,
  MODEL_ROUTER: false,
};

// ---------------------------------------------------------------------------
// Core helper: read from NEXT_PUBLIC_ env, fall back to defaults
// ---------------------------------------------------------------------------

/**
 * Returns true if NEXT_PUBLIC_FEATURE_{flag}_ENABLED === 'true'
 * or if the flag is true in FEATURE_DEFAULTS and no env override is set.
 */
export function isFeatureEnabled(flag: SliceFlag): boolean {
  const envKey = `NEXT_PUBLIC_FEATURE_${flag}_ENABLED`;
  const envValue = process.env[envKey];

  if (envValue === 'true') return true;
  if (envValue === 'false') return false;

  // No env var set — fall back to compile-time default
  return FEATURE_DEFAULTS[flag];
}

/**
 * Use inside feature slice components/routes.
 * - In development: throws a clear error so unfinished slices are obvious.
 * - In production: returns false gracefully (never crashes).
 */
export function requireFeature(flag: SliceFlag): boolean {
  const enabled = isFeatureEnabled(flag);
  if (!enabled && process.env.NODE_ENV === 'development') {
    console.warn(
      `[FeatureFlag] Slice "${flag}" is disabled. ` +
      `Set NEXT_PUBLIC_FEATURE_${flag}_ENABLED=true to enable it.`
    );
  }
  return enabled;
}

/**
 * Exhaustive record of all NEXT_PUBLIC_ env var names for documentation
 * and CI validation scripts.
 */
export const FEATURE_ENV_KEYS: Record<SliceFlag, string> = Object.fromEntries(
  (Object.keys(FEATURE_DEFAULTS) as SliceFlag[]).map((flag) => [
    flag,
    `NEXT_PUBLIC_FEATURE_${flag}_ENABLED`,
  ])
) as Record<SliceFlag, string>;
