/**
 * src/lib/api/endpoints.ts
 *
 * All BFF route constants. Single source of truth — never hardcode
 * /api/... strings in components or features.
 *
 * Pattern: ENDPOINTS.DOMAIN.action(params)
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § BFF routers + API contracts
 */

const BASE = '/api';

export const ENDPOINTS = {
  // ------------------------------------------------------------------
  // Runs
  // ------------------------------------------------------------------
  RUNS: {
    list: () => `${BASE}/runs`,
    create: () => `${BASE}/runs`,
    get: (runId: string) => `${BASE}/runs/${runId}`,
    pause: (runId: string) => `${BASE}/runs/${runId}/pause`,
    resume: (runId: string) => `${BASE}/runs/${runId}/resume`,
    stop: (runId: string) => `${BASE}/runs/${runId}/stop`,
    fork: (runId: string) => `${BASE}/runs/${runId}/fork`,
    approve: (runId: string) => `${BASE}/runs/${runId}/approve`,
    reject: (runId: string) => `${BASE}/runs/${runId}/reject`,
    compare: (left: string, right: string) =>
      `${BASE}/runs/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
  },

  // ------------------------------------------------------------------
  // Events (bootstrap history; live via Socket.IO)
  // ------------------------------------------------------------------
  EVENTS: {
    list: (runId: string) => `${BASE}/runs/${runId}/events`,
  },

  // ------------------------------------------------------------------
  // Artifacts
  // ------------------------------------------------------------------
  ARTIFACTS: {
    list: (runId: string) => `${BASE}/runs/${runId}/artifacts`,
    get: (runId: string, artifactId: string) =>
      `${BASE}/runs/${runId}/artifacts/${artifactId}`,
    listFiles: (runId: string) =>
      `${BASE}/runs/${runId}/artifacts/files`,
    diff: (runId: string, path: string) =>
      `${BASE}/runs/${runId}/artifacts/diff?path=${encodeURIComponent(path)}`,
    exportPatch: (runId: string) =>
      `${BASE}/runs/${runId}/export/patch`,
  },

  // ------------------------------------------------------------------
  // Commands
  // ------------------------------------------------------------------
  COMMANDS: {
    list: (runId: string) => `${BASE}/runs/${runId}/commands`,
    output: (runId: string, commandId: string) =>
      `${BASE}/runs/${runId}/commands/${commandId}/output`,
  },

  // ------------------------------------------------------------------
  // Traces (OTEL)
  // ------------------------------------------------------------------
  TRACES: {
    list: (runId: string) => `${BASE}/runs/${runId}/traces`,
    getSpan: (runId: string, spanId: string) =>
      `${BASE}/runs/${runId}/traces/${spanId}`,
  },

  // ------------------------------------------------------------------
  // Browser sessions
  // ------------------------------------------------------------------
  BROWSER: {
    listSessions: (runId: string) =>
      `${BASE}/runs/${runId}/browser/sessions`,
    getSession: (runId: string, sessionId: string) =>
      `${BASE}/runs/${runId}/browser/sessions/${sessionId}`,
  },

  // ------------------------------------------------------------------
  // Workspaces
  // ------------------------------------------------------------------
  WORKSPACES: {
    list: () => `${BASE}/workspaces`,
    get: (id: string) => `${BASE}/workspaces/${id}`,
    reset: (id: string) => `${BASE}/workspaces/${id}/reset`,
  },

  // ------------------------------------------------------------------
  // Agents / Presets
  // ------------------------------------------------------------------
  AGENTS: {
    listPresets: () => `${BASE}/agents/presets`,
  },

  // ------------------------------------------------------------------
  // MCP integrations
  // ------------------------------------------------------------------
  MCP: {
    list: () => `${BASE}/integrations/mcp`,
  },

  // ------------------------------------------------------------------
  // Plugins
  // ------------------------------------------------------------------
  PLUGINS: {
    list: () => `${BASE}/plugins`,
    enable: (id: string) => `${BASE}/plugins/${id}/enable`,
    disable: (id: string) => `${BASE}/plugins/${id}/disable`,
  },

  // ------------------------------------------------------------------
  // Secrets (metadata only — raw values never in UI)
  // ------------------------------------------------------------------
  SECRETS: {
    list: () => `${BASE}/secrets`,
    create: () => `${BASE}/secrets`,
    update: (id: string) => `${BASE}/secrets/${id}`,
    delete: (id: string) => `${BASE}/secrets/${id}`,
  },

  // ------------------------------------------------------------------
  // Observability
  // ------------------------------------------------------------------
  OBSERVABILITY: {
    summary: () => `${BASE}/observability/summary`,
    runs: () => `${BASE}/observability/runs`,
    errors: () => `${BASE}/observability/errors`,
  },
} as const;
