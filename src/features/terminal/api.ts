import type { TerminalCommand } from '@/lib/schemas/terminal';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function fetchRunCommands(runId: string): Promise<TerminalCommand[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/commands`);
  if (!res.ok) throw new Error(`Failed to fetch commands: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}
