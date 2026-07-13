import type { McpServer, RegisterMcpServerRequest } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchMcpServers(): Promise<McpServer[]> {
  const res = await fetch(`${BASE}/mcp`);
  if (!res.ok) throw new Error('Failed to fetch MCP servers');
  return res.json();
}

export async function registerMcpServer(body: RegisterMcpServerRequest): Promise<McpServer> {
  const res = await fetch(`${BASE}/mcp`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to register MCP server');
  return res.json();
}

export async function deleteMcpServer(id: string): Promise<void> {
  const res = await fetch(`${BASE}/mcp/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete MCP server');
}

export async function pingMcpServer(id: string): Promise<{ ok: boolean; latencyMs: number }> {
  const res = await fetch(`${BASE}/mcp/${id}/ping`, { method: 'POST' });
  if (!res.ok) throw new Error('Ping failed');
  return res.json();
}

export async function toggleMcpServer(id: string): Promise<McpServer> {
  const res = await fetch(`${BASE}/mcp/${id}/toggle`, { method: 'POST' });
  if (!res.ok) throw new Error('Toggle failed');
  return res.json();
}
