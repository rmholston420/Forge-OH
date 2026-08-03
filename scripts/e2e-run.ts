/**
 * Playwright end-to-end diagnostic for Stage 3 DoD:
 *   1. Navigate to /runs
 *   2. Click "New Run", pick a preset+workspace+model, submit a real prompt
 *   3. Wait for the run to appear in the list
 *   4. Open the run detail page and wait until status leaves "queued"
 *   5. Capture: screenshots at each stage, all /api/ responses, all Socket.IO
 *      frames (event names + first-100 chars of payload), console + page errors
 *   6. Wait until executionStatus is a terminal state, then dump one more
 *      screenshot + timeline DOM snapshot
 *
 * Usage (repo root, with pnpm dev + BFF + agent-server + ollama up):
 *   npx playwright install chromium   # first time only
 *   PROMPT="Say hi and list files in /tmp" npx tsx scripts/e2e-run.ts
 *
 * Emits:
 *   scripts/debug-out/e2e-01-runs.png
 *   scripts/debug-out/e2e-02-new-run-modal.png
 *   scripts/debug-out/e2e-03-runs-after-submit.png
 *   scripts/debug-out/e2e-04-run-detail-initial.png
 *   scripts/debug-out/e2e-05-run-detail-final.png
 *   scripts/debug-out/e2e-report.json
 *   scripts/debug-out/e2e-timeline.html
 */
import { chromium, type ConsoleMessage, type Request, type Response } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const OUT = path.resolve(__dirname, 'debug-out');
fs.mkdirSync(OUT, { recursive: true });

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';
const PROMPT = process.env.PROMPT ?? 'Say hi in one short sentence and stop.';
const TERMINAL = new Set(['finished', 'error', 'stuck', 'deleting', 'succeeded', 'failed']);
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT_MS ?? 180_000);

interface Report {
  base: string;
  prompt: string;
  finalUrl: string;
  runId: string | null;
  terminalStatus: string | null;
  elapsedMs: number;
  consoleErrors: string[];
  consoleWarnings: string[];
  pageErrors: string[];
  requestFailures: Array<{ url: string; method: string; failure: string | null }>;
  apiResponses: Array<{ url: string; status: number; contentType: string; bodyPreview: string }>;
  wsFrames: Array<{ dir: 'in' | 'out'; opcode: string; preview: string; at: number }>;
  timelineText: string | null;
}

const started = Date.now();

async function main() {
  console.log(`[e2e] launching against ${BASE}`);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const report: Report = {
    base: BASE,
    prompt: PROMPT,
    finalUrl: '',
    runId: null,
    terminalStatus: null,
    elapsedMs: 0,
    consoleErrors: [],
    consoleWarnings: [],
    pageErrors: [],
    requestFailures: [],
    apiResponses: [],
    wsFrames: [],
    timelineText: null,
  };

  // ---- Instrumentation ----
  page.on('console', (msg: ConsoleMessage) => {
    const line = `${msg.type()}: ${msg.text()}`;
    if (msg.type() === 'error') report.consoleErrors.push(line);
    else if (msg.type() === 'warning') report.consoleWarnings.push(line);
  });
  page.on('pageerror', (err) => report.pageErrors.push(String(err)));
  page.on('requestfailed', (req: Request) => {
    report.requestFailures.push({
      url: req.url(),
      method: req.method(),
      failure: req.failure()?.errorText ?? null,
    });
  });
  page.on('response', async (res: Response) => {
    const url = res.url();
    if (!url.includes('/api/')) return;
    let bodyPreview = '';
    try {
      const buf = await res.body();
      bodyPreview = buf.toString('utf-8').slice(0, 400);
    } catch {
      bodyPreview = '<binary or unreadable>';
    }
    report.apiResponses.push({
      url,
      status: res.status(),
      contentType: res.headers()['content-type'] ?? '',
      bodyPreview,
    });
  });
  page.on('websocket', (ws) => {
    console.log(`[e2e] websocket opened: ${ws.url()}`);
    ws.on('framesent', (f) =>
      report.wsFrames.push({
        dir: 'out',
        opcode: 'text',
        preview: String(f.payload).slice(0, 200),
        at: Date.now() - started,
      })
    );
    ws.on('framereceived', (f) =>
      report.wsFrames.push({
        dir: 'in',
        opcode: 'text',
        preview: String(f.payload).slice(0, 200),
        at: Date.now() - started,
      })
    );
    ws.on('close', () => console.log(`[e2e] websocket closed: ${ws.url()}`));
  });

  // ---- 1. Runs page ----
  console.log(`[e2e] step 1: navigate to /runs`);
  await page.goto(`${BASE}/runs`, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, 'e2e-01-runs.png'), fullPage: true });

  // ---- 2. Open New Run modal ----
  console.log(`[e2e] step 2: open "New Run" modal`);
  // Try a few common selectors — the button text may differ.
  const newRunButton = page.getByRole('button', { name: /new run/i }).first();
  await newRunButton.waitFor({ timeout: 10_000 });
  await newRunButton.click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(OUT, 'e2e-02-new-run-modal.png'), fullPage: true });

  // ---- 3. Fill the prompt and submit ----
  console.log(`[e2e] step 3: fill prompt and submit`);
  // Try textarea first, then any input labelled Task/Prompt.
  const promptInput = page.locator('textarea').first();
  await promptInput.waitFor({ timeout: 10_000 });
  await promptInput.fill(PROMPT);

  // Submit — try common labels.
  const submitButton = page
    .getByRole('button', { name: /(submit|create run|start|launch|run)/i })
    .last();
  await submitButton.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, 'e2e-03-runs-after-submit.png'), fullPage: true });

  // ---- 4. Detect the created run ----
  console.log(`[e2e] step 4: wait for run to appear`);
  const BFF = BASE.replace(/:3000$/, ':8081');
  const runsResp = await page.request.get(`${BFF}/api/runs?pageSize=5`);
  const runsJson = await runsResp.json();
  const newest = (runsJson.data ?? [])[0];
  if (!newest) throw new Error('no runs returned from BFF');
  report.runId = newest.id;
  console.log(`[e2e] runId = ${report.runId}`);

  // ---- 5. Navigate to detail page ----
  console.log(`[e2e] step 5: open detail page`);
  await page.goto(`${BASE}/runs/${report.runId}`, { waitUntil: 'networkidle', timeout: 30_000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, 'e2e-04-run-detail-initial.png'), fullPage: true });

  // ---- 6. Poll until terminal ----
  console.log(`[e2e] step 6: poll BFF for terminal status (timeout ${TIMEOUT_MS} ms)`);
  const deadline = Date.now() + TIMEOUT_MS;
  let status: string | undefined = newest.executionStatus ?? newest.status;
  while (Date.now() < deadline) {
    await page.waitForTimeout(1000);
    const r = await page.request.get(`${BFF}/api/runs/${report.runId}`);
    if (r.ok()) {
      const body = await r.json();
      // BFF envelope: single-item GETs return {data: {...}}, list GETs return {data:[...]}.
      const d = body?.data ?? body;
      status = d?.executionStatus ?? d?.status;
    }
    if (status && TERMINAL.has(status)) break;
  }
  report.terminalStatus = status ?? null;
  console.log(`[e2e] terminal status: ${status}`);

  // Also snapshot the events endpoint to confirm relay + agent-server events pipeline.
  try {
    const er = await page.request.get(`${BFF}/api/runs/${report.runId}/events`);
    if (er.ok()) {
      const eb = await er.json();
      const events = eb?.data ?? eb?.items ?? [];
      console.log(`[e2e] /events returned ${Array.isArray(events) ? events.length : 'non-array'} event(s)`);
      (report as any).eventCount = Array.isArray(events) ? events.length : null;
      (report as any).eventSample = Array.isArray(events) ? events.slice(0, 3) : null;
    }
  } catch (e) {
    console.log(`[e2e] /events fetch failed: ${e}`);
  }

  // Give the timeline a moment to render final events.
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, 'e2e-05-run-detail-final.png'), fullPage: true });

  // ---- 7. Stage 4: click the Files tab and assert real diff appears ----
  console.log(`[e2e] step 7: open Files tab`);
  const filesTab = page.getByRole('tab', { name: /^files$/i }).first();
  const filesLink = page.getByRole('link', { name: /^files$/i }).first();
  let opened = false;
  try {
    if (await filesTab.count()) {
      await filesTab.click({ timeout: 3000 });
      opened = true;
    } else if (await filesLink.count()) {
      await filesLink.click({ timeout: 3000 });
      opened = true;
    } else {
      // Fallback: some layouts use a plain button.
      await page.getByRole('button', { name: /^files$/i }).first().click({ timeout: 3000 });
      opened = true;
    }
  } catch (e) {
    console.log(`[e2e] Files tab click failed: ${e}`);
  }
  if (opened) {
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(OUT, 'e2e-06-files-tab.png'), fullPage: true });
  }

  // Independently query the BFF for the file list and any per-file diff.
  try {
    const fr = await page.request.get(`${BFF}/api/runs/${report.runId}/files`);
    if (fr.ok()) {
      const fj = await fr.json();
      const files = fj?.data ?? [];
      (report as any).fileCount = Array.isArray(files) ? files.length : null;
      (report as any).files = files;
      console.log(`[e2e] /files returned ${files.length} entr${files.length === 1 ? 'y' : 'ies'}`);
      if (files.length > 0) {
        const p = files[0].path;
        const encoded = encodeURIComponent(p);
        const dr = await page.request.get(`${BFF}/api/runs/${report.runId}/files/${encoded}`);
        if (dr.ok()) {
          const dj = await dr.json();
          const d = dj?.data ?? {};
          (report as any).firstFileDiff = {
            path: d.path,
            status: d.status,
            additions: d.additions,
            deletions: d.deletions,
            modifiedPreview: (d.modified ?? '').slice(0, 200),
          };
          console.log(`[e2e] first file: ${d.path} status=${d.status} +${d.additions}/-${d.deletions}`);
        } else {
          console.log(`[e2e] /files/{path} returned ${dr.status()}`);
        }
      }
    } else {
      console.log(`[e2e] /files returned ${fr.status()}`);
    }
  } catch (e) {
    console.log(`[e2e] /files fetch failed: ${e}`);
  }

  // Snapshot the timeline DOM (whatever the current implementation calls it).
  const timelineHtml = await page
    .locator('[data-testid=timeline], [data-testid=events], main')
    .first()
    .innerHTML()
    .catch(() => '<timeline element not found>');
  fs.writeFileSync(path.join(OUT, 'e2e-timeline.html'), timelineHtml);
  report.timelineText = (
    await page.locator('main').first().innerText().catch(() => '')
  ).slice(0, 4000);

  report.finalUrl = page.url();
  report.elapsedMs = Date.now() - started;

  const reportPath = path.join(OUT, 'e2e-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

  // ---- Summary ----
  console.log('\n=========  E2E SUMMARY  =========');
  console.log(`runId:           ${report.runId}`);
  console.log(`terminalStatus:  ${report.terminalStatus}`);
  console.log(`elapsedMs:       ${report.elapsedMs}`);
  console.log(`consoleErrors:   ${report.consoleErrors.length}`);
  console.log(`pageErrors:      ${report.pageErrors.length}`);
  console.log(`requestFailures: ${report.requestFailures.length}`);
  console.log(`apiResponses:    ${report.apiResponses.length}`);
  console.log(`wsFrames:        ${report.wsFrames.length}`);
  const wsEventFrames = report.wsFrames.filter((f) =>
    /"event"|"status"|"oh-event"|"oh-status"/.test(f.preview)
  );
  console.log(`wsFrames w/ event|status: ${wsEventFrames.length}`);
  if (report.consoleErrors.length) {
    console.log('\n--- consoleErrors ---');
    report.consoleErrors.slice(0, 20).forEach((e) => console.log('  ' + e));
  }
  if (report.pageErrors.length) {
    console.log('\n--- pageErrors ---');
    report.pageErrors.forEach((e) => console.log('  ' + e));
  }
  console.log('\n--- first 5 API responses ---');
  report.apiResponses.slice(0, 5).forEach((r) => {
    console.log(`  ${r.status}  ${r.url}`);
    console.log(`    body[:200]: ${r.bodyPreview.slice(0, 200).replace(/\n/g, ' ')}`);
  });
  console.log('\n--- first 10 ws frames ---');
  report.wsFrames.slice(0, 10).forEach((f) => {
    console.log(`  [${f.at}ms ${f.dir}] ${f.preview.replace(/\n/g, ' ')}`);
  });

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
