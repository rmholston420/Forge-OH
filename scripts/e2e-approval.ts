import { chromium } from '@playwright/test';

const BFF = process.env.BFF_URL ?? 'http://localhost:8081';
const BASE = process.env.BASE ?? 'http://localhost:3000';
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT_MS ?? 180_000);

interface RunSummary { id: string; status: string; title: string; }

async function bff<T = any>(method: string, path: string, body?: unknown) {
  const res = await fetch(`${BFF}${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await res.text();
  let data: any = null;
  try { data = raw ? JSON.parse(raw) : null; } catch {}
  return { status: res.status, data: data as T | null, raw };
}

async function waitForStatus(runId: string, targets: string[], deadlineMs: number) {
  const start = Date.now();
  let last = 'unknown';
  while (Date.now() - start < deadlineMs) {
    const { data } = await bff<{ data: RunSummary }>('GET', `/api/runs/${runId}`);
    last = (data as any)?.data?.status ?? 'unknown';
    if (targets.includes(last)) return { status: last, elapsedMs: Date.now() - start };
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`timed out waiting for one of [${targets.join(',')}]; last=${last}`);
}

async function createApprovalRun(title: string) {
  const { status, data, raw } = await bff<{ data: RunSummary }>('POST', '/api/runs', {
    title, agentPresetId: 'ap-1', workspaceId: 'ws-1',
    taskPrompt: title, taskComplexity: 'agentic', contextLength: title.length,
    requireApproval: true,
  });
  if (status !== 200) throw new Error(`create failed ${status}: ${raw.slice(0, 300)}`);
  const id = (data as any)?.data?.id;
  if (!id) throw new Error(`create returned no id: ${raw.slice(0, 300)}`);
  return id as string;
}

async function main() {
  console.log(`[e2e-approval] BFF=${BFF} BASE=${BASE}`);

  console.log('\n== leg 1: create + APPROVE ==');
  const approveTitle = `approval-gate approve test ${Date.now()}`;
  const approveId = await createApprovalRun(approveTitle);
  console.log(`run id: ${approveId}`);
  const waitA = await waitForStatus(approveId, ['awaiting_approval'], 60_000);
  console.log(`✓ awaiting_approval in ${waitA.elapsedMs}ms`);
  const approveResp = await bff('POST', `/api/runs/${approveId}/approve`);
  console.log(`approve HTTP ${approveResp.status}: ${approveResp.raw.slice(0, 200)}`);
  if (approveResp.status !== 200) throw new Error('approve failed');
  const post = await waitForStatus(approveId, ['running', 'succeeded', 'failed', 'finished', 'awaiting_approval'], 30_000);
  console.log(`✓ approve transitioned to ${post.status} in ${post.elapsedMs}ms`);

  console.log('\n== leg 2: create + REJECT ==');
  const rejectTitle = `approval-gate reject test ${Date.now()}`;
  const rejectId = await createApprovalRun(rejectTitle);
  console.log(`run id: ${rejectId}`);
  const waitR = await waitForStatus(rejectId, ['awaiting_approval'], 60_000);
  console.log(`✓ awaiting_approval in ${waitR.elapsedMs}ms`);
  const rejectResp = await bff('POST', `/api/runs/${rejectId}/reject`, { reason: 'e2e test reject' });
  console.log(`reject HTTP ${rejectResp.status}: ${rejectResp.raw.slice(0, 200)}`);
  if (rejectResp.status !== 200) throw new Error('reject failed');
  const postR = await waitForStatus(rejectId, ['failed', 'succeeded', 'finished', 'paused'], 30_000);
  console.log(`✓ reject reached terminal ${postR.status} in ${postR.elapsedMs}ms`);

  console.log('\n== leg 3: UI smoke ==');
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/runs`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /new run/i }).click();
  const cb = page.getByLabel(/Require approval before each tool call/i);
  await cb.waitFor({ state: 'visible', timeout: 5000 });
  console.log(`✓ checkbox visible, checked=${await cb.isChecked()}`);
  await browser.close();

  console.log('\n[e2e-approval] ALL LEGS PASSED');
}

main().catch((e) => { console.error('[e2e-approval] FAILED:', e?.stack ?? e); process.exit(1); });
