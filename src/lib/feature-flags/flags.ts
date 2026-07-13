/**
 * src/lib/feature-flags/flags.ts
 *
 * Canonical registry of all Forge-OH feature flags.
 *
 * Every slice in the build spec requires:
 *   "Feature flag gating FEATURE_[SLICE_NAME]_ENABLED"
 *
 * Naming rule: FEATURE_{SLICE_CODE} where SLICE_CODE is the
 * identifier used in Forge-OH-Build-Plan-Definitive.md.
 *
 * Each flag maps to the environment variable:
 *   NEXT_PUBLIC_FEATURE_{SLICE_CODE}=true|false
 *
 * All flags default to FALSE unless explicitly enabled in .env.local.
 * Enable slices incrementally as they reach the Definition of Done.
 */

export const FEATURE_FLAGS = {
  // ------------------------------------------------------------------
  // Phase 0 — Foundation
  // ------------------------------------------------------------------
  /** BFF connected to OpenHands; Socket.IO live streaming wired up */
  LIVE_STREAM: 'LIVE_STREAM',

  // ------------------------------------------------------------------
  // Phase 1 — Run Command Centre
  // ------------------------------------------------------------------
  /** 1A: Run List — paginated run list with status badges */
  RUN_LIST: 'RUN_LIST',
  /** 1B: Run Detail Shell — shell + tab bar */
  RUN_DETAIL_SHELL: 'RUN_DETAIL_SHELL',
  /** 1C: Plan Rail — plan step tree */
  PLAN_RAIL: 'PLAN_RAIL',
  /** 1D: Event Timeline — live event feed */
  EVENT_TIMELINE: 'EVENT_TIMELINE',
  /** 1E: Approval Gate — HITL approve/reject */
  APPROVAL_GATE: 'APPROVAL_GATE',

  // ------------------------------------------------------------------
  // Phase 2 — Artifact & Code Intelligence
  // ------------------------------------------------------------------
  /** 2A: Artifact Viewer — diff viewer + file tree */
  ARTIFACT_VIEWER: 'ARTIFACT_VIEWER',
  /** 2B: Terminal Pane — xterm.js terminal */
  TERMINAL_PANE: 'TERMINAL_PANE',
  /** 2C: Browser Pane — embedded browser viewer */
  BROWSER_PANE: 'BROWSER_PANE',
  /** 2D: Metrics Pane — recharts run metrics */
  METRICS_PANE: 'METRICS_PANE',

  // ------------------------------------------------------------------
  // Phase 3 — Configuration Hub
  // ------------------------------------------------------------------
  /** 3A: Workspace Manager */
  WORKSPACE_MANAGER: 'WORKSPACE_MANAGER',
  /** 3B: Agent Preset Manager */
  AGENT_PRESETS: 'AGENT_PRESETS',
  /** 3C: MCP Integration Panel */
  MCP_PANEL: 'MCP_PANEL',
  /** 3D: Secrets Vault */
  SECRETS_VAULT: 'SECRETS_VAULT',

  // ------------------------------------------------------------------
  // Phase 4 — Observability Suite
  // ------------------------------------------------------------------
  /** 4A: Observability Overview — KPI dashboard */
  OBSERVABILITY_OVERVIEW: 'OBSERVABILITY_OVERVIEW',
  /** 4B: Loop Guard Monitor — loop detection UI */
  LOOP_GUARD_MONITOR: 'LOOP_GUARD_MONITOR',
  /** 4C: Trace Viewer — OTEL span explorer */
  TRACE_VIEWER: 'TRACE_VIEWER',

  // ------------------------------------------------------------------
  // Phase 5 — Plugin & Extension Layer
  // ------------------------------------------------------------------
  /** 5A: Plugin Marketplace */
  PLUGIN_MARKETPLACE: 'PLUGIN_MARKETPLACE',
  /** 5B: Run Replay */
  RUN_REPLAY: 'RUN_REPLAY',
  /** 5C: Rigpa-LMS Integration (RBAC, course enrollment) */
  RIGPA_LMS: 'RIGPA_LMS',
} as const;

export type FeatureFlag = (typeof FEATURE_FLAGS)[keyof typeof FEATURE_FLAGS];
