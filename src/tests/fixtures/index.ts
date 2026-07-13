/**
 * Forge-OH MSW Fixture barrel — single source of truth for all mock data.
 * Import from here in MSW handlers and test files.
 *
 * Canonical fixture files: *.fixture.ts
 * Deterministic IDs:       seed.ts
 */
export { SEED } from './seed';
export { mockRuns } from './runs.fixture';
export { mockEvents } from './events.fixture';
export { mockWorkspaces } from './workspaces.fixture';
export { mockPlugins } from './plugins.fixture';
export { mockSecrets } from './secrets.fixture';
export { mockMCPServers } from './mcp.fixture';
