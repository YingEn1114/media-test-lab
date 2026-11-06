import { test, expect, request as apiRequest } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const fixture = fileURLToPath(new URL('../fixtures/e2e-upload.mp4', import.meta.url));

async function login(page) {
  await page.goto('/accounts/login/', { waitUntil: 'networkidle' });
  await page.locator('#id_login').fill('admin');
  await page.locator('#id_password').fill('MediaCMS@123');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page).not.toHaveURL(/accounts\/login/);
}

test('上传：真实上传视频文件', async ({ page }) => {
  await login(page);
  await page.goto('/upload', { waitUntil: 'networkidle' });
  await page.locator('input[name="qqfile"]').setInputFiles(fixture);
  await expect(page.locator('body')).toContainText('e2e-upload.mp4', { timeout: 30000 });
  await expect(page.locator('body')).toContainText(/查看媒体|open_in_new/);

  // 清理：找到刚上传媒体的查看链接，用 API Token 删除，避免测试数据堆积
  const token = process.env.MEDIACMS_TOKEN;
  if (token) {
    const link = page.getByRole('link', { name: /查看媒体|view media|open_in_new/i }).first();
    const href = await link.getAttribute('href').catch(() => null);
    const mediaToken = href?.match(/[?&]m=([^&]+)/)?.[1];
    if (mediaToken) {
      const api = await apiRequest.newContext({
        baseURL: process.env.BASE_URL || 'http://localhost',
        extraHTTPHeaders: { Authorization: `Token ${token}` },
      });
      const res = await api.delete(`/api/v1/media/${mediaToken}`);
      console.log(`cleanup media ${mediaToken}: HTTP ${res.status()}`);
      await api.dispose();
    }
  }
});
