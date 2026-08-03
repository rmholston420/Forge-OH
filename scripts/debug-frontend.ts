/**
 * Playwright diagnostic — run against a live pnpm dev at http://localhost:3000
 *
 * Usage (from repo root, with `pnpm dev` and BFF already running):
 *   npx playwright install chromium   # first time only
 *   npx tsx scripts/debug-frontend.ts
 *
 * Emits:
 *   scripts/debug-out/runs.png                — screenshot of /runs
 *   scripts/debug-out/runs-report.json        — console/network summary
 */
import { chromium, type ConsoleMessage, type Request, type Response } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const OUT = path.resolve(__dirname, 'debug-out');
fs.mkdirSync(OUT, { recursive: true });

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';

interface Report {
  finalUrl: string;
  consoleErrors: string[];
  consoleWarnings: string[];
  consoleLogs: string[];
  pageErrors: string[];
  requestFailures: Array<{ url: string; method: string; failure: string | null }>;
  apiResponses: Array<{ url: string; status: number; contentType: string; bodyPreview: string }>;
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const report: Report = {
    finalUrl: '',
    consoleErrors: [],
    consoleWarnings: [],
    consoleLogs: [],
    pageErrors: [],
    requestFailures: [],
    apiResponses: [],
  };

  page.on('console', (msg: ConsoleMessage) => {
    const line = `${msg.type()}: ${msg.text()}`;
    if (msg.type() === 'error') report.consoleErrors.push(line);
    else if (msg.type() === 'warning') report.consoleWarnings.push(line);
    else report.consoleLogs.push(line);
  });

  page.on('pageerror', (err) => {
    report.pageErrors.push(String(err));
  });

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
      bodyPreview = buf.toString('utf-8').slice(0, 300);
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

  console.log(`[debug] navigating to ${BASE}/runs`);
  await page.goto(`${BASE}/runs`, { waitUntil: 'networkidle', timeout: 30_000 });

  // Give React Query a beat to settle.
  await page.waitForTimeout(1500);

  report.finalUrl = page.url();

  const shot = path.join(OUT, 'runs.png');
  await page.screenshot({ path: shot, fullPage: true });
  console.log(`[debug] screenshot -> ${shot}`);

  const reportPath = path.join(OUT, 'runs-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`[debug] report -> ${reportPath}`);

  // Terse console summary
  console.log('\n=========  SUMMARY  =========');
  console.log(`finalUrl:          ${report.finalUrl}`);
  console.log(`consoleErrors:     ${report.consoleErrors.length}`);
  console.log(`pageErrors:        ${report.pageErrors.length}`);
  console.log(`requestFailures:   ${report.requestFailures.length}`);
  console.log(`api responses:     ${report.apiResponses.length}`);
  for (const r of report.apiResponses) {
    console.log(`   ${r.status}  ${r.url}`);
    console.log(`        content-type: ${r.contentType}`);
    console.log(`        body[:300]:   ${r.bodyPreview.replace(/\n/g, ' ')}`);
  }
  if (report.consoleErrors.length) {
    console.log('\n--- consoleErrors ---');
    report.consoleErrors.forEach((e) => console.log('  ' + e));
  }
  if (report.pageErrors.length) {
    console.log('\n--- pageErrors ---');
    report.pageErrors.forEach((e) => console.log('  ' + e));
  }
  if (report.requestFailures.length) {
    console.log('\n--- requestFailures ---');
    report.requestFailures.forEach((f) => console.log(`  ${f.method} ${f.url} -> ${f.failure}`));
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
