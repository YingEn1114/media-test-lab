import { test, expect, request as apiRequest } from '@playwright/test';

async function login(page) {
  await page.goto('/accounts/login/', { waitUntil: 'networkidle' });
  await page.locator('#id_login').fill('admin');
  await page.locator('#id_password').fill('MediaCMS@123');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page).not.toHaveURL(/accounts\/login/);
}

test('搜索：结果包含 Test Video', async ({ page }) => {
  await page.goto('/search?q=Test', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/MediaCMS/);
  await expect(page.locator('body')).toContainText('result for "Test"');
  await expect(page.locator('body')).toContainText('Test Video');
});

test('分类页：加载分类列表', async ({ page }) => {
  await page.goto('/categories', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/Categories/);
  await expect(page.locator('body')).toContainText('Art');
  await expect(page.locator('body')).toContainText('Documentary');
});

test('登录：admin 登录成功', async ({ page }) => {
  await login(page);
  await expect(page.locator('body')).toContainText('Test Video');
  await expect(page.locator('body')).toContainText(/Upload|上传/);
});

test('上传：未登录访问跳转登录页', async ({ page }) => {
  await page.goto('/upload', { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/accounts\/login/);
});

test('上传：登录后上传页可用', async ({ page }) => {
  await login(page);
  await page.goto('/upload', { waitUntil: 'networkidle' });
  await expect(page.locator('input[name="qqfile"]')).toHaveCount(1);
  await expect(page.locator('body')).toContainText(/Upload|上传/);
});

test('评论：登录后视频页有评论输入框', async ({ page }) => {
  await login(page);
  await page.goto('/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  const box = page.locator('textarea').first();
  await expect(box).toBeVisible();
});

test('评论：提交成功', async ({ page }) => {
  await login(page);
  await page.goto('/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  const text = `E2E 评论 ${Date.now()}`;
  await page.locator('textarea').first().fill(text);
  await page.getByRole('button', { name: /提交|submit/i }).click();
  await expect(page.locator('body')).toContainText(text, { timeout: 15000 });
  await expect(page.locator('body')).toContainText(/评论|comment/i);

  const token = process.env.MEDIACMS_TOKEN;
  if (token) {
    const api = await apiRequest.newContext({
      baseURL: process.env.BASE_URL || 'http://localhost',
      extraHTTPHeaders: { Authorization: `Token ${token}` },
    });
    const list = await (await api.get('/api/v1/media/juMSnf8VT/comments')).json();
    const items = Array.isArray(list) ? list : list.results || [];
    const comment = items.find((c) => c.text === text);
    if (comment?.uid) {
      const res = await api.delete(`/api/v1/media/juMSnf8VT/comments/${comment.uid}`);
      console.log(`cleanup comment ${comment.uid}: HTTP ${res.status()}`);
    }
    await api.dispose();
  }
});
