import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

function attachBrowserMonitors(page: import('@playwright/test').Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const requestFailures: string[] = [];
  const apiFailures: string[] = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(`[console:${msg.type()}] ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    pageErrors.push(`[pageerror] ${String(err)}`);
  });

  page.on('requestfailed', req => {
    requestFailures.push(
      `[requestfailed] ${req.method()} ${req.url()} :: ${req.failure()?.errorText ?? 'unknown'}`
    );
  });

  page.on('response', async res => {
    const url = res.url();
    if (url.includes('/api/') || url.includes(':8081')) {
      if (res.status() >= 400) {
        let body = '';
        try {
          body = (await res.text()).slice(0, 1500);
        } catch {}
        apiFailures.push(`[response:${res.status()}] ${url}\n${body}`);
      }
    }
  });

  return { consoleErrors, pageErrors, requestFailures, apiFailures };
}

async function writeArtifacts(name: string, payload: Record<string, unknown>) {
  const outDir = path.join(process.cwd(), 'playwright-artifacts');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(
    path.join(outDir, `${name}.json`),
    JSON.stringify(payload, null, 2),
    'utf-8'
  );
}

async function assertClean(
  name: string,
  page: import('@playwright/test').Page,
  monitor: ReturnType<typeof attachBrowserMonitors>
) {
  await writeArtifacts(name, {
    url: page.url(),
    title: await page.title(),
    consoleErrors: monitor.consoleErrors,
    pageErrors: monitor.pageErrors,
    requestFailures: monitor.requestFailures,
    apiFailures: monitor.apiFailures,
  });

  expect(monitor.consoleErrors, `${name}: console errors`).toEqual([]);
  expect(monitor.pageErrors, `${name}: page errors`).toEqual([]);
  expect(monitor.requestFailures, `${name}: request failures`).toEqual([]);
  expect(monitor.apiFailures, `${name}: API failures`).toEqual([]);
}

test('triage login page render', async ({ browser }) => {
  const page = await browser.newPage();
  const monitor = attachBrowserMonitors(page);

  await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('body')).toBeVisible();
  await assertClean('login-page', page, monitor);
  await page.close();
});

test('triage authenticated runs page', async ({ page }) => {
  const monitor = attachBrowserMonitors(page);

  await page.goto('/runs', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('body')).toBeVisible();
  await expect(page).toHaveURL(/\/runs/);

  await assertClean('runs-page', page, monitor);
});

test('triage run detail page', async ({ page }) => {
  const monitor = attachBrowserMonitors(page);

  await page.goto('/runs/run-new-001', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await expect(page.locator('body')).toBeVisible();

  await assertClean('run-detail-page', page, monitor);
});

test('triage new run composer modal', async ({ page }) => {
  const monitor = attachBrowserMonitors(page);

  await page.goto('/runs', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('body')).toBeVisible();

  const newRunButton = page.getByRole('button', { name: /new run/i }).first();
  await expect(newRunButton).toBeVisible();
  await newRunButton.click();

  const prompt = page.locator('textarea, [placeholder*="Describe what you want"], [name="prompt"]').first();
  await expect(prompt).toBeVisible();
  await prompt.fill('Create a small test run from Playwright triage.');

  const selects = page.locator('select');
  const selectCount = await selects.count();

  for (let i = 0; i < selectCount; i++) {
    await expect(selects.nth(i)).toBeVisible();
  }

  await page.waitForTimeout(1500);

  await assertClean('new-run-composer-modal', page, monitor);
});
