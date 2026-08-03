/**
 * Stage 6 verifier v2:
 *   1. /workspaces lists the seeded workspace with its real path
 *   2. Create modal has NO Type select (docker/e2b/modal gone)
 *   3. /runs "New Run" composer picker shows workspace names without (type) suffix
 *   4. Launched run's agent-server working_dir == selected workspace's path
 *
 * Prereqs (on Colossus):
 *   - agent-server on http://127.0.0.1:8090
 *   - BFF on http://127.0.0.1:8081
 *   - Next dev on http://localhost:3000
 *   - At least one workspace registered
 *
 * Run: node --experimental-strip-types ./scripts/e2e-stage6.ts
 */
import { chromium } from '@playwright/test';

const BFF = 'http://127.0.0.1:8081';
const OH  = 'http://127.0.0.1:8090';
const UI  = 'http://localhost:3000';

const fail = (m: string) => { console.error('FAIL:', m); process.exit(1); };
const pass = (m: string) => console.log('PASS:', m);

async function main() {
  const wsList = await (await fetch(`${BFF}/api/workspaces`)).json();
  if (!Array.isArray(wsList) || wsList.length === 0) fail('no workspaces to test with');
  const ws = wsList[0];
  console.log(`ground truth: id=${ws.id} name=${ws.name} path=${ws.path}`);

  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('console', (m) => {
    const t = m.type();
    if (t === 'error' || t === 'warning') console.log(`[browser ${t}]`, m.text());
  });

  await page.goto(`${UI}/workspaces`, { waitUntil: 'networkidle' });
  const wsBody = await page.locator('body').innerText();
  if (!wsBody.includes(ws.name)) fail(`workspace name "${ws.name}" not visible on /workspaces`);
  if (!wsBody.includes(ws.path)) fail(`workspace path "${ws.path}" not visible on /workspaces`);
  pass('/workspaces shows name + path');

  await page.getByRole('button', { name: /new workspace/i }).first().click();
  await page.waitForSelector('input#ws-name');
  const typeSelectCount = await page.locator('select#ws-type').count();
  if (typeSelectCount !== 0) fail(`Type select still present (count=${typeSelectCount})`);
  const dockerImageField = await page.locator('input#ws-image').count();
  const remoteUrlField = await page.locator('input#ws-url').count();
  if (dockerImageField || remoteUrlField) fail('docker/remote form fields still present');
  pass('New Workspace modal has no Type/docker/remote fields');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  await page.goto(`${UI}/runs`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /^new run$/i }).first().click();
  await page.waitForSelector('select#run-workspace', { timeout: 5000 });
  const runWsSelect = page.locator('select#run-workspace');
  const optionTexts = await runWsSelect.locator('option').allTextContents();
  console.log('workspace options:', optionTexts);
  if (optionTexts.some((t) => /\(local\)/i.test(t))) fail('workspace option still has "(local)" suffix');
  if (!optionTexts.some((t) => t.includes(ws.name))) fail(`workspace "${ws.name}" not in picker`);
  pass('workspace picker labels clean');

  await runWsSelect.selectOption(ws.id);
  await page.fill('textarea#run-title', 'stage6-verifier: echo hello');
  const launchBtn = page.getByRole('button', { name: /launch run/i });
  await launchBtn.waitFor({ state: 'visible', timeout: 3000 });
  const presetOptions = await page.locator('select#run-preset option').all();
  if (presetOptions.length > 0) {
    const values = await Promise.all(presetOptions.map((o) => o.getAttribute('value')));
    const firstNonEmpty = values.find((v) => v && v !== '');
    if (firstNonEmpty) await page.selectOption('select#run-preset', firstNonEmpty);
  }
  await launchBtn.click();

  await page.waitForURL(/\/runs\/[a-f0-9-]+/, { timeout: 15_000 });
  const runId = page.url().split('/runs/')[1].split(/[/?#]/)[0];
  console.log(`launched run: ${runId}`);

  let workingDir: string | undefined;
  for (let i = 0; i < 30; i++) {
    try {
      const conv = await (await fetch(`${OH}/api/conversations/${runId}`)).json();
      workingDir = conv?.workspace?.working_dir ?? conv?.working_dir;
      if (workingDir) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  if (!workingDir) fail('agent-server conversation did not expose working_dir');
  if (workingDir !== ws.path) fail(`working_dir=${workingDir} does not match workspace path=${ws.path}`);
  pass(`agent-server working_dir == workspace path (${workingDir})`);

  await browser.close();
  console.log('\nSTAGE 6 VERIFIED');
}

main().catch((e) => { console.error(e); process.exit(1); });
