import { test, expect } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 });

test('移动端首页与播放页', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/MediaCMS/);
  await expect(page.locator('body')).toContainText('Test Video');
  await page.screenshot({ path: 'screenshots/mobile-home.png', fullPage: false });

  await page.goto('/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
  await expect(page.locator('.video-js')).toBeVisible();
  await expect(page.locator('.video-js video')).toHaveCount(1);
  await page.screenshot({ path: 'screenshots/mobile-video.png', fullPage: false });
});
