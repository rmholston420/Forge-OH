import type { TerminalCommand } from '@/lib/schemas/terminal';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export async function fetchRunCommands(runId: string): Promise<TerminalCommand[]> {
  const res = await fetch(`${BFF}/api/runs/${runId}/commands`);
  if (!res.ok) throw new Error(`Failed to fetch commands: ${res.status}`);
  const json = await res.json();
  return json.data ?? [];
}

// -------------------------------------------------------------------------
// Live bash (Slice C.1)
// -------------------------------------------------------------------------

export interface BashEvent {
  id: string;
  kind: 'BashCommand' | 'BashOutput';
  commandId: string;
  timestamp: string;
  order: number;
  command?: string | null;
  cwd?: string | null;
  stdout?: string | null;
  stderr?: string | null;
  exitCode: number | null;
}

export interface StartBashResponse {
  data: BashEvent;
}

export async function startBash(
  runId: string,
  body: { command: string; cwd?: string | null; timeout?: number },
): Promise<BashEvent> {
  const res = await fetch(`${BFF}/api/runs/${runId}/bash`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`start_bash failed: ${res.status} ${await res.text()}`);
  const json: StartBashResponse = await res.json();
  return json.data;
}

export function bashStreamUrl(
  runId: string,
  commandId: string,
  fromOrder = -1,
): string {
  const p = new URLSearchParams({
    command_id: commandId,
    from_order: String(fromOrder),
  });
  return `${BFF}/api/runs/${runId}/bash/stream?${p.toString()}`;
}

