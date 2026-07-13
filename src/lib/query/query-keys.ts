export const QUERY_KEYS = {
  runs: {
    list: () => ['runs'] as const,
    detail: (id: string) => ['runs', id] as const,
    events: (id: string) => ['runs', id, 'events'] as const,
    artifacts: (id: string) => ['runs', id, 'artifacts'] as const,
    commands: (id: string) => ['runs', id, 'commands'] as const,
    traces: (id: string) => ['runs', id, 'traces'] as const,
    presets: () => ['runs', 'presets'] as const,
  },
  workspaces: {
    list: () => ['workspaces'] as const,
    detail: (id: string) => ['workspaces', id] as const,
  },
  secrets: {
    list: () => ['secrets'] as const,
  },
  plugins: {
    list: () => ['plugins'] as const,
  },
  mcp: {
    list: () => ['mcp'] as const,
  },
  observability: {
    summary: () => ['observability', 'summary'] as const,
  },
};
