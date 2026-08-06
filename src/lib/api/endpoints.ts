/**
 * src/lib/api/endpoints.ts
 *
 * All BFF route constants. Single source of truth — never hardcode
 * /api/... strings in components or features.
 *
 * Pattern: ENDPOINTS.DOMAIN.action(params)
 *
 * These constants MUST match the actual BFF routes (see bff/routers/*.py).
 * The wiring audit at forge-oh-wiring-audit.md tracks drift between this
 * registry and the BFF surface.
 */

const BASE = '/api';

export const ENDPOINTS = {
  // ------------------------------------------------------------------
  // Runs (bff/routers/runs.py)
  // ------------------------------------------------------------------
  RUNS: {
    list: () => `${BASE}/runs`,
    create: () => `${BASE}/runs`,
    get: (runId: string) => `${BASE}/runs/${runId}`,
    plan: (runId: string) => `${BASE}/runs/${runId}/plan`,
    pause: (runId: string) => `${BASE}/runs/${runId}/pause`,
    resume: (runId: string) => `${BASE}/runs/${runId}/resume`,
    stop: (runId: string) => `${BASE}/runs/${runId}/stop`,
    fork: (runId: string) => `${BASE}/runs/${runId}/fork`,
    // Stage 6.4c — restart-from-here (ADR-026): full re-create of a run
    // whose worktree is provisioned at the anchor event's captured sha and
    // whose first user message replays the anchor's text.  Distinct from
    // fork (conversation-only branch) because it also resets the working
    // tree; distinct from create (needs source-run continuity).
    restart: (runId: string) => `${BASE}/runs/${runId}/restart`,
    approve: (runId: string) => `${BASE}/runs/${runId}/approve`,
    reject: (runId: string) => `${BASE}/runs/${runId}/reject`,
    message: (runId: string) => `${BASE}/runs/${runId}/message`,
    secrets: (runId: string) => `${BASE}/runs/${runId}/secrets`,
    // Stage 3.4 — the BFF endpoint at bff/routers/runs.py::compare_runs
    // takes `base` + `fork` query keys. The previous `left` / `right`
    // spelling was a stale helper contract with no live callers.
    compare: (baseId: string, forkId: string) =>
      `${BASE}/runs/compare?base=${encodeURIComponent(baseId)}&fork=${encodeURIComponent(forkId)}`,
  },

  // ------------------------------------------------------------------
  // Events (bootstrap history; live via Socket.IO)
  // ------------------------------------------------------------------
  EVENTS: {
    list: (runId: string) => `${BASE}/runs/${runId}/events`,
  },

  // ------------------------------------------------------------------
  // Artifacts — BFF only exposes list. Per-artifact/diff/export are
  // stubbed in the runs router today; see BUILD_LOG for follow-up slice.
  // ------------------------------------------------------------------
  ARTIFACTS: {
    list: (runId: string) => `${BASE}/runs/${runId}/artifacts`,
  },

  // ------------------------------------------------------------------
  // Commands (terminal reconstruction)
  // ------------------------------------------------------------------
  COMMANDS: {
    list: (runId: string) => `${BASE}/runs/${runId}/commands`,
  },

  // ------------------------------------------------------------------
  // Traces (OTEL) — per-run trace list only. Trace/span detail is under
  // OBSERVABILITY below.
  // ------------------------------------------------------------------
  TRACES: {
    list: (runId: string) => `${BASE}/runs/${runId}/traces`,
  },

  // ------------------------------------------------------------------
  // Browser frames (reconstructed from browser-tool ActionEvents)
  // ------------------------------------------------------------------
  BROWSER: {
    frames: (runId: string) => `${BASE}/runs/${runId}/browser`,
  },

  // ------------------------------------------------------------------
  // File diffs (reconstructed from file-write ActionEvents)
  // ------------------------------------------------------------------
  FILES: {
    list: (runId: string) => `${BASE}/runs/${runId}/files`,
    get: (runId: string, filePath: string) =>
      `${BASE}/runs/${runId}/files/${encodeURIComponent(filePath)}`,
  },

  // ------------------------------------------------------------------
  // Workspaces (bff/routers/workspaces.py)
  // ------------------------------------------------------------------
  WORKSPACES: {
    list: () => `${BASE}/workspaces`,
    get: (id: string) => `${BASE}/workspaces/${id}`,
    create: () => `${BASE}/workspaces`,
    update: (id: string) => `${BASE}/workspaces/${id}`,
    delete: (id: string) => `${BASE}/workspaces/${id}`,
    test: (id: string) => `${BASE}/workspaces/${id}/test`,
  },

  // ------------------------------------------------------------------
  // Agent presets (bff/routers/agent_presets.py)
  // ------------------------------------------------------------------
  // Stage 2.1 — inference backend health inventory
  // (bff/routers/inference_backends.py)
  INFERENCE_BACKENDS: {
    list: () => `${BASE}/inference-backends`,
  },

  AGENTS: {
    listPresets: () => `${BASE}/agent-presets`,
    getPreset: (id: string) => `${BASE}/agent-presets/${id}`,
    createPreset: () => `${BASE}/agent-presets`,
    updatePreset: (id: string) => `${BASE}/agent-presets/${id}`,
    deletePreset: (id: string) => `${BASE}/agent-presets/${id}`,
    duplicatePreset: (id: string) => `${BASE}/agent-presets/${id}/duplicate`,
    setDefaultPreset: (id: string) => `${BASE}/agent-presets/${id}/set-default`,
  },

  // ------------------------------------------------------------------
  // MCP integrations (bff/routers/mcp.py — passthrough to agent-server
  // settings/mcp/{name})
  // ------------------------------------------------------------------
  MCP: {
    list: () => `${BASE}/mcp`,
    create: () => `${BASE}/mcp`,
    delete: (id: string) => `${BASE}/mcp/${id}`,
    ping: (id: string) => `${BASE}/mcp/${id}/ping`,
    toggle: (id: string) => `${BASE}/mcp/${id}/toggle`,
  },

  // ------------------------------------------------------------------
  // Plugins (bff/routers/plugins.py)
  // ------------------------------------------------------------------
  PLUGINS: {
    list: () => `${BASE}/plugins`,
    marketplace: () => `${BASE}/plugins/marketplace`,
    create: () => `${BASE}/plugins`,
    install: () => `${BASE}/plugins/install`,
    enable: (id: string) => `${BASE}/plugins/${id}/enable`,
    disable: (id: string) => `${BASE}/plugins/${id}/disable`,
    uninstall: (id: string) => `${BASE}/plugins/${id}`,
    ping: (id: string) => `${BASE}/plugins/${id}/ping`,
  },

  // ------------------------------------------------------------------
  // Secrets (bff/routers/secrets.py)
  // ------------------------------------------------------------------
  SECRETS: {
    list: () => `${BASE}/secrets`,
    create: () => `${BASE}/secrets`,
    rotate: (id: string) => `${BASE}/secrets/${id}/rotate`,
    delete: (id: string) => `${BASE}/secrets/${id}`,
  },

  // ------------------------------------------------------------------
  // Notifications (bff/routers/notifications.py)
  // ------------------------------------------------------------------
  NOTIFICATIONS: {
    list: () => `${BASE}/notifications`,
    markRead: (id: string) => `${BASE}/notifications/${id}/read`,
    markAllRead: () => `${BASE}/notifications/read-all`,
    delete: (id: string) => `${BASE}/notifications/${id}`,
  },

  // ------------------------------------------------------------------
  // Metrics (bff/routers/metrics.py)
  // ------------------------------------------------------------------
  METRICS: {
    // Frontend dashboard endpoints
    summary: (period: string) => `${BASE}/metrics/summary?period=${period}`,
    daily: (period: string) => `${BASE}/metrics/daily?period=${period}`,
    models: (period: string) => `${BASE}/metrics/models?period=${period}`,
    workspaces: (period: string) =>
      `${BASE}/metrics/workspaces?period=${period}`,
    // Per-entity legacy endpoints
    global: () => `${BASE}/metrics`,
    forRun: (runId: string) => `${BASE}/metrics/runs/${runId}`,
    forWorkspace: (workspaceId: string) =>
      `${BASE}/metrics/workspaces/${workspaceId}`,
    cost: () => `${BASE}/metrics/cost`,
  },

  // ------------------------------------------------------------------
  // Settings (bff/routers/settings.py)
  // ------------------------------------------------------------------
  SETTINGS: {
    get: () => `${BASE}/settings`,
    patch: () => `${BASE}/settings`,
    reset: () => `${BASE}/settings/reset`,
    modelRouting: () => `${BASE}/settings/model-routing`,
  },

  // ------------------------------------------------------------------
  // Observability (bff/routers/observability.py)
  // ------------------------------------------------------------------
  OBSERVABILITY: {
    traces: () => `${BASE}/observability/traces`,
    tracesForRun: (runId: string) =>
      `${BASE}/observability/runs/${runId}/traces`,
    trace: (traceId: string) => `${BASE}/observability/traces/${traceId}`,
    spans: (traceId: string) =>
      `${BASE}/observability/traces/${traceId}/spans`,
  },

  // ------------------------------------------------------------------
  // RepoGraph (bff/routers/repograph.py — Slice D)
  // ------------------------------------------------------------------
  REPOGRAPH: {
    health: () => `${BASE}/repograph/health`,
    index: () => `${BASE}/repograph/index`,
    search: (repoKey: string, q: string, limit = 20) =>
      `${BASE}/repograph/search?repo_key=${encodeURIComponent(repoKey)}` +
      `&q=${encodeURIComponent(q)}&limit=${limit}`,
    callers: (repoKey: string, name: string, relPath?: string, limit = 20) => {
      const rp = relPath
        ? `&rel_path=${encodeURIComponent(relPath)}`
        : '';
      return (
        `${BASE}/repograph/callers?repo_key=${encodeURIComponent(repoKey)}` +
        `&name=${encodeURIComponent(name)}${rp}&limit=${limit}`
      );
    },
    callees: (repoKey: string, relPath: string, limit = 20) =>
      `${BASE}/repograph/callees?repo_key=${encodeURIComponent(repoKey)}` +
      `&rel_path=${encodeURIComponent(relPath)}&limit=${limit}`,
    coChanged: (
      repoKey: string,
      relPath: string,
      window = 50,
      limit = 10,
    ) =>
      `${BASE}/repograph/co_changed?repo_key=${encodeURIComponent(repoKey)}` +
      `&rel_path=${encodeURIComponent(relPath)}&window=${window}&limit=${limit}`,
    contextBundle: () => `${BASE}/repograph/context_bundle`,
    graph: (repoKey: string, limit = 500) =>
      `${BASE}/repograph/graph?repo_key=${encodeURIComponent(repoKey)}` +
      `&limit=${limit}`,
  },

  // ------------------------------------------------------------------
  // Trajectory memory (bff/routers/trajectories.py) — Slice F
  // ------------------------------------------------------------------
  TRAJECTORIES: {
    list: (params?: {
      limit?: number;
      status?: string;
      repoKey?: string;
    }) => {
      const qs: string[] = [];
      if (params?.limit !== undefined) qs.push(`limit=${params.limit}`);
      if (params?.status) qs.push(`status=${encodeURIComponent(params.status)}`);
      if (params?.repoKey)
        qs.push(`repo_key=${encodeURIComponent(params.repoKey)}`);
      const q = qs.length ? `?${qs.join('&')}` : '';
      return `${BASE}/trajectories${q}`;
    },
    get: (trajectoryId: string) =>
      `${BASE}/trajectories/${encodeURIComponent(trajectoryId)}`,
    search: () => `${BASE}/trajectories/search`,
  },
} as const;
