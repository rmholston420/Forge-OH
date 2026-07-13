import type { PluginListResponse } from '../../../lib/schemas/plugin';

const now = new Date().toISOString();
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const pluginsFixture: PluginListResponse = {
  total: 3,
  plugins: [
    {
      id: 'plugin-github',
      name: 'GitHub Integration',
      version: '2.1.0',
      description: 'Create PRs, browse issues, and clone repos directly from agent runs',
      author: 'Forge-OH Team',
      status: 'enabled',
      updatedAt: ago(3 * 24 * 60 * 60 * 1000),
      installedAt: ago(7 * 24 * 60 * 60 * 1000),
    },
    {
      id: 'plugin-jira',
      name: 'Jira Connector',
      version: '1.0.3',
      description: 'Link runs to Jira tickets and update ticket status from run outcomes',
      author: 'Community',
      status: 'disabled',
      updatedAt: ago(5 * 24 * 60 * 60 * 1000),
      installedAt: ago(10 * 24 * 60 * 60 * 1000),
    },
    {
      id: 'plugin-slack',
      name: 'Slack Notifications',
      version: '1.2.1',
      description: 'Post run status updates and approval requests to Slack channels',
      author: 'Forge-OH Team',
      status: 'enabled',
      updatedAt: ago(1 * 24 * 60 * 60 * 1000),
      installedAt: ago(4 * 24 * 60 * 60 * 1000),
    },
  ],
};
