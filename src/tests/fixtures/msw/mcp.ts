const now = new Date().toISOString();
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const mcpServersFixture = {
  total: 2,
  servers: [
    {
      id: 'mcp-filesystem',
      name: 'Filesystem MCP',
      type: 'stdio',
      description: 'Provides file read/write/list tools to the agent',
      status: 'connected',
      toolCount: 6,
      tools: ['read_file', 'write_file', 'list_directory', 'create_directory', 'delete_file', 'move_file'],
      connectedAt: ago(30 * 60 * 1000),
      updatedAt: now,
    },
    {
      id: 'mcp-browser',
      name: 'Playwright Browser MCP',
      type: 'stdio',
      description: 'Headless browser automation via Playwright',
      status: 'connected',
      toolCount: 9,
      tools: ['navigate', 'click', 'type', 'screenshot', 'scroll', 'wait', 'evaluate', 'select', 'hover'],
      connectedAt: ago(30 * 60 * 1000),
      updatedAt: now,
    },
  ],
};
