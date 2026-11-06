import { test, expect } from '@playwright/test';

const HLS = '/media/hls/4b2c62d9ee1e4643af54949706180754/master.m3u8';

test('视频播放器：HLS 清单 + 播放/暂停', async ({ page, request }) => {
  const res = await request.get(HLS);
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain('#EXTM3U');

  await page.goto('/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
  await expect(page.locator('.video-js')).toBeVisible();
  await expect(page.locator('.video-js video')).toHaveCount(1);
  const video = page.locator('.video-js video').first();
  await page.waitForFunction(() => {
    const v = document.querySelector('.video-js video');
    return v && v.readyState >= 3 && v.duration > 0;
  });

  const info = await video.evaluate((v) => ({
    duration: v.duration,
    width: v.videoWidth,
    height: v.videoHeight,
  }));
  expect(info.duration).toBeGreaterThan(5);
  expect(info.width).toBe(640);
  expect(info.height).toBe(360);

  const played = await video.evaluate(async (v) => {
    v.muted = true;
    await v.play();
    return true;
  });
  expect(played).toBe(true);
  await page.waitForTimeout(1500);
  expect(await video.evaluate((v) => v.currentTime)).toBeGreaterThan(0.3);

  await video.evaluate((v) => v.pause());
  expect(await video.evaluate((v) => v.paused)).toBe(true);
  await page.screenshot({ path: 'screenshots/video.png' });
});
