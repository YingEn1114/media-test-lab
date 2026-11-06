import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
await page.goto('http://localhost:8081/#/login', { waitUntil: 'networkidle' });
await page.locator('.login-form input').first().fill('admin');
await page.locator('.login-form input[type="password"]').fill('metersphere');
await page.locator('button[type="submit"]').first().click();
await page.waitForTimeout(3500);

// 点顶部项目选择器
await page.getByText('示例项目', { exact: true }).first().click().catch(async () => {
  await page.locator('.arco-select').first().click();
});
await page.waitForTimeout(1000);
console.log('DROPDOWN:', (await page.locator('body').innerText()).slice(0, 300).replace(/\n/g,' | '));
await page.getByText('MediaCMS 测试项目', { exact: true }).first().click();
await page.waitForTimeout(2500);
console.log('AFTER SWITCH URL:', page.url());
console.log('AFTER SWITCH TEXT:', (await page.locator('body').innerText()).slice(0, 400).replace(/\n/g,' | '));

await page.goto('http://localhost:8081/#/api-test/management', { waitUntil: 'networkidle' });
await page.waitForTimeout(3000);
const text = await page.locator('body').innerText();
console.log('MANAGEMENT URL:', page.url());
console.log('HAS 74:', text.includes('74'), 'HAS MediaCMS:', text.includes('MediaCMS'), 'HAS 用例:', text.includes('用例'));
console.log('TEXT:', text.slice(0, 1500).replace(/\n/g,' | '));
await page.screenshot({ path: 'ms-mediacms-project.png', fullPage: false });
await browser.close();
