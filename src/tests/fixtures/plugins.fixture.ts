export type PluginStatus = 'installed' | 'enabled' | 'disabled' | 'update_available' | 'error';

export interface PluginFixture {
  id: string;
  name: string;
  description: string;
  version: string;
  status: PluginStatus;
  author: string;
}

export const mockPlugins: PluginFixture[] = [
  {
    id: 'plugin-001',
    name: 'GitHub Integration',
    description: 'Create PRs, review code, manage issues directly from Forge-OH runs.',
    version: '1.2.0',
    status: 'enabled',
    author: 'Forge-OH Team',
  },
  {
    id: 'plugin-002',
    name: 'Continue.dev Autocomplete',
    description: 'FIM-optimized IDE autocomplete via Codestral 22B local model.',
    version: '0.9.1',
    status: 'disabled',
    author: 'Continue.dev',
  },
];
