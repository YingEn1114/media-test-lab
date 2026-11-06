import { test, expect } from '@playwright/test';

const VIDEO = '/view?m=juMSnf8VT';

async function openVideo(page) {
  await page.goto(VIDEO, { waitUntil: 'networkidle' });
  await expect(page.locator('.video-js')).toBeVisible();
  await expect(page.locator('.video-js video')).toHaveCount(1);
  const video = page.locator('.video-js video').first();
  await page.waitForFunction(() => {
    const v = document.querySelector('.video-js video');
    return v && v.readyState >= 3 && v.duration > 0;
  });
  return video;
}

test('播放器控件：静音与音量', async ({ page }) => {
  const video = await openVideo(page);
  const mute = page.locator('.vjs-mute-control');
  await expect(mute).toBeVisible();

  await mute.click();
  expect(await video.evaluate((v) => v.muted)).toBe(true);
  await mute.click();
  expect(await video.evaluate((v) => v.muted)).toBe(false);

  await video.evaluate((v) => { v.volume = 0.3; });
  expect(await video.evaluate((v) => v.volume)).toBeCloseTo(0.3, 1);
});

test('播放器控件：进度条 seek', async ({ page }) => {
  const video = await openVideo(page);
  const progress = await page.locator('.vjs-progress-control').boundingBox();
  expect(progress).not.toBeNull();
  await page.mouse.click(progress.x + progress.width * 0.6, progress.y + progress.height / 2);
  await page.waitForTimeout(500);
  expect(await video.evaluate((v) => v.currentTime)).toBeGreaterThan(2);
});

test('播放器控件：倍速设置', async ({ page }) => {
  const video = await openVideo(page);
  await page.locator('.vjs-settings-button').click();
  await page.getByText('Playback speed', { exact: false }).first().click();
  await page.getByText('1.5', { exact: true }).click();
  await page.waitForTimeout(300);
  expect(await video.evaluate((v) => v.playbackRate)).toBe(1.5);
});

test('播放器控件：全屏', async ({ page }) => {
  await openVideo(page);
  await page.locator('.vjs-fullscreen-control').click();
  await page.waitForTimeout(500);
  const isFullscreen = await page.evaluate(() => !!document.fullscreenElement);
  expect(isFullscreen).toBe(true);
  await page.keyboard.press('Escape');
});

test('播放器控件：设置菜单包含倍速与清晰度', async ({ page }) => {
  await openVideo(page);
  await page.locator('.vjs-settings-button').click();
  const text = await page.locator('.video-js').innerText();
  expect(text).toContain('Playback speed');
  expect(text).toContain('Quality');
});

test('播放器：弱网下 HLS 仍能加载', async ({ page }) => {
  await page.route('**/*.m3u8', async (route) => {
    await new Promise((r) => setTimeout(r, 1200));
    await route.continue();
  });
  const video = await openVideo(page);
  expect(await video.evaluate((v) => v.duration)).toBeGreaterThan(5);
});
