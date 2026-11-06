import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
await page.locator('.vjs-settings-button').click();
await page.waitForTimeout(500);
console.log('SETTINGS TEXT:', JSON.stringify((await page.locator('.video-js').innerText()).slice(0, 500)));
console.log('MENU ITEMS:', JSON.stringify(await page.locator('.vjs-menu-item').allInnerTexts()));

await page.goto('http://localhost/accounts/login/', { waitUntil: 'networkidle' });
const inputs = await page.evaluate(() => Array.from(document.querySelectorAll('input')).map(i => ({name:i.name, type:i.type, id:i.id, placeholder:i.placeholder})));
console.log('LOGIN INPUTS:', JSON.stringify(inputs, null, 2));
console.log('LOGIN BUTTONS:', JSON.stringify(await page.locator('button, input[type=submit]').evaluateAll(els => els.map(e => ({tag:e.tagName, text:(e.innerText||e.value||'').trim(), type:e.type})))));
await browser.close();
