import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto('http://localhost:3000/runs', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /new run/i }).click().catch(() => {});
  await page.waitForTimeout(1500);
  const cb = page.getByLabel(/Require approval before each tool call/i);
  const found = await cb.count();
  console.log('APPROVAL_GATE checkbox count:', found);
  if (found > 0) {
    console.log('checked?:', await cb.isChecked());
  } else {
    const modal = await page.locator('form').first().innerHTML().catch(() => '(no form)');
    console.log('---form HTML (first 2500 chars)---');
    console.log(modal.slice(0, 2500));
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
