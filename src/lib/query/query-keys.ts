/**
 * Centralized, hierarchical TanStack Query key registry.
 * All keys are typed tuples for surgical cache invalidation.
 */
export const queryKeys = {
  runs: {
    all: () => ['runs'] as const,
    list: () => ['runs', 'list'] as const,
    detail: (id: string) => ['runs', 'detail', id] as const,
    events: (id: string) => ['runs', 'events', id] as const,
    files: (id: string) => ['runs', 'files', id] as const,
    fileDiff: (id: string, path: string) => ['runs', 'diff', id, path] as const,
    commands: (id: string) => ['runs', 'commands', id] as const,
    artifacts: (id: string) => ['runs', 'artifacts', id] as const,
    traces: (id: string) => ['runs', 'traces', id] as const,
    plan: (id: string) => ['runs', 'plan', id] as const,
  },
  agents: {
    presets: () => ['agents', 'presets'] as const,
  },
  workspaces: {
    all: () => ['workspaces'] as const,
    list: () => ['workspaces', 'list'] as const,
    detail: (id: string) => ['workspaces', 'detail', id] as const,
  },
  mcp: {
    all: () => ['mcp'] as const,
    list: () => ['mcp', 'list'] as const,
    detail: (id: string) => ['mcp', 'detail', id] as const,
  },
  plugins: {
    all: () => ['plugins'] as const,
    list: () => ['plugins', 'list'] as const,
    detail: (id: string) => ['plugins', 'detail', id] as const,
  },
  secrets: {
    all: () => ['secrets'] as const,
    list: () => ['secrets', 'list'] as const,
  },
  observability: {
    summary: () => ['observability', 'summary'] as const,
    traces: () => ['observability', 'traces'] as const,
    trace: (id: string) => ['observability', 'trace', id] as const,
  },
  browser: {
    sessions: (runId: string) => ['browser', 'sessions', runId] as const,
  },
} as const;
