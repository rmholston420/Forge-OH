export type MCPServerStatus = 'connected' | 'warning' | 'disconnected';

export interface MCPServerFixture {
  id: string;
  name: string;
  status: MCPServerStatus;
  toolCount: number;
  authState: 'authenticated' | 'unauthenticated' | 'error';
  lastCallAt: string | null;
  errorMessage?: string;
}

export const mockMCPServers: MCPServerFixture[] = [
  {
    id: 'mcp-001',
    name: 'Filesystem MCP',
    status: 'connected',
    toolCount: 8,
    authState: 'authenticated',
    lastCallAt: new Date(Date.now() - 30000).toISOString(),
  },
  {
    id: 'mcp-002',
    name: 'GitHub MCP',
    status: 'warning',
    toolCount: 14,
    authState: 'unauthenticated',
    lastCallAt: null,
    errorMessage: 'Token missing — set GITHUB_TOKEN in secrets.',
  },
];
