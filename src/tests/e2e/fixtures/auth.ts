import { test as base, type Page } from '@playwright/test';
import path from 'path';

function authStatePath(role: string) {
  return path.join(process.cwd(), '.auth', `${role}.json`);
}

type AuthFixtures = {
  adminPage:     Page;
  developerPage: Page;
  viewerPage:    Page;
};

export const test = base.extend<AuthFixtures>({
  adminPage: async ({ browser }, use) => {
    const ctx  = await browser.newContext({ storageState: authStatePath('admin') });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },
  developerPage: async ({ browser }, use) => {
    const ctx  = await browser.newContext({ storageState: authStatePath('developer') });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },
  viewerPage: async ({ browser }, use) => {
    const ctx  = await browser.newContext({ storageState: authStatePath('viewer') });
    const page = await ctx.newPage();
    await use(page);
    await ctx.close();
  },
});

export { expect } from '@playwright/test';
