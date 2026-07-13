/**
 * src/lib/schemas/mcp.ts
 *
 * Zod v4 schema for the Integration / MCP Server domain object.
 *
 * Domain name: Integration (canonical — do not rename)
 * Ref: Forge-OH-Build-Plan-Definitive.md § Domain Model
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// MCPTool — a single tool exposed by an MCP server
// ---------------------------------------------------------------------------

export const MCPToolSchema = z.object({
  name: z.string(),
  description: z.string().optional(),
  inputSchema: z.record(z.unknown()).optional(),
});

export type MCPTool = z.infer<typeof MCPToolSchema>;

// ---------------------------------------------------------------------------
// MCPServer status — matches state language in design spec
// ---------------------------------------------------------------------------

export const MCPServerStatusSchema = z.enum([
  'connected',
  'warning',
  'disconnected',
  'error',
]);

export type MCPServerStatus = z.infer<typeof MCPServerStatusSchema>;

// ---------------------------------------------------------------------------
// MCPServer (Integration domain object)
// ---------------------------------------------------------------------------

export const MCPServerSchema = z.object({
  id: z.string(),
  name: z.string(),
  url: z.string().url(),
  status: MCPServerStatusSchema,
  toolCount: z.number().int().nonnegative(),
  tools: z.array(MCPToolSchema).optional(),
  /** OAuth / API-key auth state */
  authState: z.enum(['authenticated', 'unauthenticated', 'expired']),
  lastCallAt: z.string().datetime().nullable(),
  lastError: z.string().nullable(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type MCPServer = z.infer<typeof MCPServerSchema>;

// ---------------------------------------------------------------------------
// List response
// ---------------------------------------------------------------------------

export const MCPServerListSchema = z.array(MCPServerSchema);
export type MCPServerList = z.infer<typeof MCPServerListSchema>;
