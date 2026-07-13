/**
 * Centralized TanStack Query key registry.
 * Every feature domain owns a namespace here.
 * Hierarchy: [domain, ...specifics]
 */
export const runKeys = {
  all:     ['runs']                    as const,
  lists:   () => ['runs', 'list']      as const,
  detail:  (id: string) => ['runs', 'detail', id] as const,
  events:  (id: string) => ['runs', 'events', id] as const,
  plan:    (id: string) => ['runs', 'plan',   id] as const,
  files:   (id: string) => ['runs', 'files',  id] as const,
  diff:    (id: string, path: string) => ['runs', 'diff', id, path] as const,
  presets: () => ['runs', 'presets']   as const,
};

export const workspaceKeys = {
  all:    ['workspaces']                        as const,
  detail: (id: string) => ['workspaces', id]    as const,
};

export const agentKeys = {
  all:     ['agents']                           as const,
  presets: () => ['agents', 'presets']          as const,
  detail:  (id: string) => ['agents', id]       as const,
};

export const mcpKeys = {
  all:     ['mcp']                as const,
  servers: ['mcp', 'servers']    as const,
  server:  (id: string) => ['mcp', 'servers', id] as const,
};

export const pluginKeys = {
  all:    ['plugins']             as const,
  detail: (id: string) => ['plugins', id] as const,
};

export const secretKeys = {
  all:   ['secrets'] as const,
  lists: () => ['secrets', 'list'] as const,
};

export const observabilityKeys = {
  all:     ['observability']                              as const,
  summary: () => ['observability', 'summary']            as const,
  metrics: (runId: string) => ['observability', 'metrics', runId] as const,
};

export const traceKeys = {
  spans: (runId: string) => ['trace', 'spans', runId] as const,
};

export const browserKeys = {
  frames: (runId: string) => ['browser', 'frames', runId] as const,
};

export const artifactKeys = {
  list: (runId: string) => ['artifacts', runId] as const,
};

export const terminalKeys = {
  commands: (runId: string) => ['terminal', 'commands', runId] as const,
};

export const settingsKeys = {
  all: ['settings'] as const,
};

export const notificationKeys = {
  all: ['notifications'] as const,
};
