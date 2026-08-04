/**
 * Thin wrappers around BFF `/api/selfeval` endpoints. Matches the
 * pattern in ``src/features/metrics/api.ts`` so it composes with the
 * existing @tanstack/react-query setup without any store changes.
 */

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export interface CycleListItem {
  filename: string;
  started_at: string | null;
  finished_at: string | null;
  manifest_path: string | null;
  selection_strategy: string | null;
  tasks_selected: number;
  tasks_passed: number;
  tasks_failed: number;
  tasks_timed_out: number;
  tasks_errored: number;
}

export interface TaskOutcome {
  task_id: string;
  run_id: string | null;
  verdict: 'passed' | 'failed' | 'timeout' | 'error';
  reason: string | null;
  duration_sec: number | null;
  verify_verdict: string | null;
  final_status: string | null;
}

export interface CycleSummary {
  started_at: string;
  finished_at: string;
  manifest_path: string;
  selection_strategy: string;
  tasks_selected: number;
  tasks_passed: number;
  tasks_failed: number;
  tasks_timed_out: number;
  tasks_errored: number;
  outcomes: TaskOutcome[];
}

export interface ProposalListItem {
  filename: string;
  size_bytes: number;
  modified_at: string;
}

export interface Proposal {
  filename: string;
  body: string;
}

export interface RunStatus {
  running: boolean;
  started_at: string | null;
  last_result: Record<string, unknown> | null;
}

export interface RunResponse {
  started_at: string;
  service_unit: string;
}

async function _json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}

// NOTE: `.then(_json)` cannot infer the generic `T` on _json<T>, so TS falls
// back to `unknown` and every fetch* return type explodes. Pass the generic
// explicitly via an arrow wrapper so each call site pins its own T.
// Regression guard: slice/selfeval-frontend-polish rebuild on Colossus hit
// "Type 'unknown' is not assignable to type '{ cycles: CycleListItem[]; }'".

export const fetchCycles = (): Promise<{ cycles: CycleListItem[] }> =>
  fetch(`${BASE}/api/selfeval/cycles`).then((r) => _json<{ cycles: CycleListItem[] }>(r));

export const fetchCycle = (filename: string): Promise<CycleSummary> =>
  fetch(`${BASE}/api/selfeval/cycles/${encodeURIComponent(filename)}`).then((r) =>
    _json<CycleSummary>(r),
  );

export const fetchProposals = (
  date?: string,
): Promise<{ proposals: ProposalListItem[] }> => {
  const qs = date ? `?date=${encodeURIComponent(date)}` : '';
  return fetch(`${BASE}/api/selfeval/proposals${qs}`).then((r) =>
    _json<{ proposals: ProposalListItem[] }>(r),
  );
};

export const fetchProposal = (filename: string): Promise<Proposal> =>
  fetch(`${BASE}/api/selfeval/proposals/${encodeURIComponent(filename)}`).then((r) =>
    _json<Proposal>(r),
  );

export const fetchStatus = (): Promise<RunStatus> =>
  fetch(`${BASE}/api/selfeval/status`).then((r) => _json<RunStatus>(r));

export const postRun = (): Promise<RunResponse> =>
  fetch(`${BASE}/api/selfeval/run`, { method: 'POST' }).then((r) => _json<RunResponse>(r));
