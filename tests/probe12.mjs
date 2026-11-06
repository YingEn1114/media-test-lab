import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const resp = await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
console.log('status', resp?.status(), 'url', page.url(), 'title', await page.title());
console.log('video count', await page.locator('video').count(), 'videojs', await page.locator('.video-js').count());
console.log('body', (await page.locator('body').innerText()).slice(0, 300).replace(/\n/g,' | '));
await browser.close();
