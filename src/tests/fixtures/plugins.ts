import type { Plugin } from '@/lib/schemas/plugin';

export const mockPlugins: Plugin[] = [
  {
    id: 'plugin-git',
    name: 'Git Integration',
    description: 'Native git operations: branch, commit, push, PR creation.',
    version: '1.2.0',
    status: 'enabled',
    author: 'Forge-OH Core',
    installedAt: '2026-07-01T00:00:00.000Z',
  },
  {
    id: 'plugin-linter',
    name: 'ESLint + Ruff',
    description: 'Inline linting feedback for TypeScript and Python files.',
    version: '2.0.1',
    status: 'enabled',
    author: 'Forge-OH Core',
    installedAt: '2026-07-01T00:00:00.000Z',
  },
  {
    id: 'plugin-search',
    name: 'Semantic Code Search',
    description: 'Semantic search across the workspace using embeddings.',
    version: '0.9.4',
    status: 'update_available',
    author: 'Community',
    installedAt: '2026-07-06T00:00:00.000Z',
  },
  {
    id: 'plugin-browser',
    name: 'Browser Automation',
    description: 'Playwright-based browser control for web scraping and testing.',
    version: '1.0.0',
    status: 'disabled',
    author: 'Forge-OH Core',
    installedAt: '2026-07-01T00:00:00.000Z',
  },
];
