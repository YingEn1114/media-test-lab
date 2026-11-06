import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
await page.goto('http://localhost:8081/#/login', { waitUntil: 'networkidle' });
await page.locator('.login-form input').first().fill('admin');
await page.locator('.login-form input[type="password"]').fill('metersphere');
await page.locator('button[type="submit"]').first().click();
await page.waitForTimeout(3500);
const info = await page.evaluate(() => {
  const nodes = Array.from(document.querySelectorAll('*')).filter(e => e.childElementCount === 0 && (e.textContent || '').trim() === '示例项目');
  return nodes.map(e => {
    const r = e.getBoundingClientRect();
    return { tag: e.tagName, cls: e.className, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), parent: e.parentElement?.className, gp: e.parentElement?.parentElement?.className };
  });
});
console.log(JSON.stringify(info, null, 2));
console.log('HEADER HTML:', (await page.locator('header').first().innerHTML().catch(()=>'no header')).slice(0, 1000));
await browser.close();
