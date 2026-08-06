export const runKeys = {
  all: ['runs'] as const,
  lists: () => ['runs', 'list'] as const,
  list: (filters?: Record<string, unknown>) => ['runs', 'list', filters ?? {}] as const,
  detail: (runId: string) => ['runs', runId] as const,
  events: (runId: string) => ['runs', runId, 'events'] as const,
  plan: (runId: string) => ['runs', runId, 'plan'] as const,
  files: (runId: string) => ['runs', runId, 'files'] as const,
  artifacts: (runId: string) => ['runs', runId, 'artifacts'] as const,
  commands: (runId: string) => ['runs', runId, 'commands'] as const,
  traces: (runId: string) => ['runs', runId, 'traces'] as const,
  presets: () => ['runs', 'presets'] as const,
};

export const agentKeys = {
  all: ['agents'] as const,
  presets: () => ['agents', 'presets'] as const,
  detail: (id: string) => ['agents', id] as const,
};

// Stage 2.1 — inference backend health inventory
export const inferenceBackendKeys = {
  all: ['inference-backends'] as const,
  list: () => ['inference-backends', 'list'] as const,
};

export const workspaceKeys = {
  all: ['workspaces'] as const,
  lists: () => ['workspaces', 'list'] as const,
  list: (filters?: Record<string, unknown>) => ['workspaces', 'list', filters ?? {}] as const,
  detail: (id: string) => ['workspaces', id] as const,
};

export const secretKeys = {
  all: ['secrets'] as const,
  lists: () => ['secrets', 'list'] as const,
  list: (filters?: Record<string, unknown>) => ['secrets', 'list', filters ?? {}] as const,
  detail: (id: string) => ['secrets', id] as const,
};

export const settingsKeys = {
  all: ['settings'] as const,
  current: () => ['settings', 'current'] as const,
};

export const notificationKeys = {
  all: ['notifications'] as const,
  list: () => ['notifications', 'list'] as const,
};

export const observabilityKeys = {
  all: ['observability'] as const,
  summary: (filters?: Record<string, unknown>) => ['observability', filters ?? {}] as const,
};

export const trajectoryKeys = {
  all: ['trajectories'] as const,
  list: (filters?: Record<string, unknown>) =>
    ['trajectories', 'list', filters ?? {}] as const,
  detail: (id: string) => ['trajectories', 'detail', id] as const,
  search: (query: Record<string, unknown>) =>
    ['trajectories', 'search', query] as const,
};

export const QUERY_KEYS = {
  runs: runKeys,
  runKeys,
  agentKeys,
  inferenceBackends: inferenceBackendKeys,
  inferenceBackendKeys,
  workspaces: workspaceKeys,
  workspaceKeys,
  secrets: secretKeys,
  secretKeys,
  settingsKeys,
  notificationKeys,
  observability: observabilityKeys,
  observabilityKeys,
  trajectories: trajectoryKeys,
  trajectoryKeys,
  plugins: {
    all: ['plugins'] as const,
    detail: (id: string) => ['plugins', id] as const,
  },
  mcp: {
    all: ['mcp'] as const,
    detail: (id: string) => ['mcp', id] as const,
  },
  repograph: {
    all: ['repograph'] as const,
    health: () => ['repograph', 'health'] as const,
    search: (repoKey: string, q: string) =>
      ['repograph', 'search', repoKey, q] as const,
    callers: (repoKey: string, name: string, relPath?: string) =>
      ['repograph', 'callers', repoKey, name, relPath ?? null] as const,
    callees: (repoKey: string, relPath: string) =>
      ['repograph', 'callees', repoKey, relPath] as const,
    coChanged: (repoKey: string, relPath: string) =>
      ['repograph', 'coChanged', repoKey, relPath] as const,
    contextBundle: (repoKey: string, seeds: string[]) =>
      ['repograph', 'contextBundle', repoKey, [...seeds].sort()] as const,
  },
} as const;
