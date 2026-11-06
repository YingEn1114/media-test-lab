import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
await page.goto('http://localhost:8081/#/login', { waitUntil: 'networkidle' });
await page.locator('.login-form input').first().fill('admin');
await page.locator('.login-form input[type="password"]').fill('metersphere');
await page.locator('button[type="submit"]').first().click();
await page.waitForTimeout(3500);
const top = await page.evaluate(() => Array.from(document.querySelectorAll('body *')).filter(e => {
  const r = e.getBoundingClientRect();
  return r.y >= 0 && r.y < 130 && r.width > 0 && r.height > 0 && (e.textContent || '').includes('示例项目');
}).slice(0, 8).map(e => {
  const r = e.getBoundingClientRect();
  return { tag: e.tagName, cls: String(e.className).slice(0,120), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
}));
console.log(JSON.stringify(top, null, 2));
await browser.close();
