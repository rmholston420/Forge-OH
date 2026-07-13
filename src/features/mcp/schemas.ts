import { z } from 'zod';

export const McpTransportSchema = z.enum(['stdio', 'sse', 'http']);
export type McpTransport = z.infer<typeof McpTransportSchema>;

export const McpStatusSchema = z.enum(['connected', 'disconnected', 'error', 'connecting']);
export type McpStatus = z.infer<typeof McpStatusSchema>;

export const McpServerSchema = z.object({
  id:          z.string(),
  name:        z.string().min(1).max(64),
  description: z.string().optional(),
  transport:   McpTransportSchema,
  command:     z.string().optional(),   // stdio only
  url:         z.string().url().optional(), // sse / http only
  status:      McpStatusSchema,
  toolCount:   z.number().int().min(0),
  lastPingMs:  z.number().optional(),
  lastSeenAt:  z.string().datetime().optional(),
  tags:        z.array(z.string()).default([]),
  enabled:     z.boolean().default(true),
});
export type McpServer = z.infer<typeof McpServerSchema>;

export const RegisterMcpServerSchema = z.discriminatedUnion('transport', [
  z.object({
    transport:   z.literal('stdio'),
    name:        z.string().min(1),
    command:     z.string().min(1, 'Command is required for stdio transport'),
    description: z.string().optional(),
    tags:        z.array(z.string()).default([]),
  }),
  z.object({
    transport:   z.literal('sse'),
    name:        z.string().min(1),
    url:         z.string().url('Must be a valid URL'),
    description: z.string().optional(),
    tags:        z.array(z.string()).default([]),
  }),
  z.object({
    transport:   z.literal('http'),
    name:        z.string().min(1),
    url:         z.string().url('Must be a valid URL'),
    description: z.string().optional(),
    tags:        z.array(z.string()).default([]),
  }),
]);
export type RegisterMcpServerRequest = z.infer<typeof RegisterMcpServerSchema>;
