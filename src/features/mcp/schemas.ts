export * from '@/lib/schemas/mcp';
export type {
  McpServer as MCPServer,
  McpServerStatus as MCPServerStatus,
  McpStatus as McpStatus,
  RegisterMcpServerRequest as RegisterMcpServerRequest,
} from '@/lib/schemas/mcp';

export type PluginStatus =
  | 'installed'
  | 'enabled'
  | 'disabled'
  | 'updateavailable'
  | 'error'
  | 'installing';

export interface Plugin {
  id: string;
  name: string;
  version: string;
  status?: PluginStatus;
  baseUrl?: string;
  authType?: string;
  capabilities: string[];
  description?: string;
  author?: string;
  configSchema?: Record<string, unknown>;
  installedAt?: string;
}
