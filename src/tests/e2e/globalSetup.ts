import { chromium, type FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';

const USERS = [
  { role: 'admin',     email: 'admin@forge.dev',  password: 'password123' },
  { role: 'developer', email: 'dev@forge.dev',    password: 'password123' },
  { role: 'viewer',    email: 'viewer@forge.dev', password: 'password123' },
] as const;

export default async function globalSetup(config: FullConfig) {
  const authDir = path.join(process.cwd(), '.auth');
  fs.mkdirSync(authDir, { recursive: true });

  const browser = await chromium.launch();

  for (const user of USERS) {
    const page = await browser.newPage();
    await page.goto(`${BASE_URL}/login`);

    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: /sign in/i }).click();

    await page.waitForURL(`${BASE_URL}/runs`, { timeout: 10_000 });
    await page.context().storageState({ path: path.join(authDir, `${user.role}.json`) });
    await page.close();
  }

  await browser.close();
}
