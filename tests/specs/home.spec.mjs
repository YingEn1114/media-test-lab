import { test, expect } from '@playwright/test';

test('首页加载与导航', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/MediaCMS/);
  await expect(page.locator('body')).toContainText('Test Video');
  expect(await page.locator('a[href*="/view?m="]').count()).toBeGreaterThan(0);
  await page.screenshot({ path: 'screenshots/home.png', fullPage: true });
});
