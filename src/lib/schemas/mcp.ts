import { z } from 'zod';

export const McpServerStatusSchema = z.enum(['connected', 'disconnected', 'error', 'disabled', 'warning', 'connecting']);
export type McpServerStatus = z.infer<typeof McpServerStatusSchema>;
export type McpStatus = McpServerStatus;

export const McpToolSchema = z.object({
  name: z.string(),
  description: z.string().default(''),
  inputSchema: z.record(z.string(), z.unknown()).default({}),
});

export const McpServerSchema = z.object({
  id: z.string(),
  name: z.string(),
  url: z.string().default(''),
  transport: z.enum(['stdio', 'http', 'sse']).default('stdio'),
  enabled: z.boolean().default(true),
  tools: z.array(McpToolSchema).default([]),
  toolCount: z.number().default(0),
  tags: z.array(z.string()).default([]),
  lastPingMs: z.number().optional(),
  lastPingAt: z.string().optional(),
  version: z.string().optional(),
  description: z.string().optional(),
  status: McpServerStatusSchema.default('disconnected'),
});

export const RegisterMcpServerRequestSchema = z.object({
  name: z.string(),
  url: z.string().optional(),
  transport: z.enum(['stdio', 'http', 'sse']).default('stdio'),
  enabled: z.boolean().default(true),
});

export type McpTool = z.infer<typeof McpToolSchema>;
export type McpServer = Partial<z.infer<typeof McpServerSchema>> & Pick<z.infer<typeof McpServerSchema>, 'id' | 'name'>;
export type MCPServer = McpServer;
export type RegisterMcpServerRequest = z.infer<typeof RegisterMcpServerRequestSchema>;
