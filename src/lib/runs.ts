export type Run = {
  id: string;
  title: string;
  status: string;
  agentPresetName: string;
  workspaceId: string;
  workspaceType: string;
  activeTool: string | null;
  updatedAt: string;
  createdAt: string;
  elapsedMs: number | null;
  estimatedCostUsd: number | null;
};

export type RunListResponse = {
  items: Run[];
  total: number;
};

export type CreateRunInput = {
  task: string;
  title?: string;
};

export async function fetchRuns(): Promise<RunListResponse> {
  const res = await fetch("/api/runs", {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to load runs");
  }

  return res.json();
}

export async function fetchRun(runId: string): Promise<Run> {
  const res = await fetch(`/api/runs/${runId}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to load run ${runId}`);
  }

  return res.json();
}

export async function createRun(input: CreateRunInput): Promise<Run> {
  const res = await fetch("/api/runs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!res.ok) {
    throw new Error("Failed to create run");
  }

  return res.json();
}
