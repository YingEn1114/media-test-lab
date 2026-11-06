import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
await page.goto('http://localhost:8081/#/login', { waitUntil: 'networkidle' });
await page.locator('.login-form input').first().fill('admin');
await page.locator('.login-form input[type="password"]').fill('metersphere');
await page.locator('button[type="submit"]').first().click();
await page.waitForTimeout(3500);

const nodes = page.getByText('示例项目', { exact: true });
const n = await nodes.count();
console.log('nodes', n);
let picked = false;
for (let i = 0; i < n; i++) {
  const box = await nodes.nth(i).boundingBox();
  console.log(i, box);
  if (box && box.y < 130 && box.width > 0) { await nodes.nth(i).click(); picked = true; break; }
}
console.log('picked', picked);
await page.waitForTimeout(800);
const opts = page.locator('.arco-select-option');
console.log('options', await opts.count(), JSON.stringify(await opts.allInnerTexts()));
const target = opts.filter({ hasText: 'MediaCMS' }).first();
if (await target.count()) { await target.click(); } else { console.log('no MediaCMS option'); }
await page.waitForTimeout(2500);
console.log('URL', page.url());
console.log('TOP TEXT', (await page.locator('body').innerText()).slice(0, 250).replace(/\n/g,' | '));
await browser.close();
