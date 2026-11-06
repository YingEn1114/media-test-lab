import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
await page.waitForTimeout(1000);
await page.locator('.vjs-settings-button').click();
await page.getByText('Playback speed', { exact: false }).first().click().catch(e=>console.log('speed click err', e.message));
await page.waitForTimeout(400);
console.log('SPEED MENU:', JSON.stringify(await page.locator('.video-js').innerText()));
console.log('MENU ITEMS:', JSON.stringify(await page.locator('.vjs-menu-item').allInnerTexts()));

// login
await page.goto('http://localhost/accounts/login/', { waitUntil: 'networkidle' });
await page.locator('#id_login').fill('admin');
await page.locator('#id_password').fill('MediaCMS@123');
await page.getByRole('button', { name: 'Sign In' }).click();
await page.waitForTimeout(2500);
console.log('AFTER LOGIN URL:', page.url());
console.log('AFTER LOGIN TEXT:', (await page.locator('body').innerText()).slice(0, 200).replace(/\n/g,' | '));

await page.goto('http://localhost/upload', { waitUntil: 'networkidle' });
console.log('UPLOAD URL:', page.url());
console.log('UPLOAD INPUTS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('input')).map(i=>({name:i.name,type:i.type,id:i.id})))));
console.log('UPLOAD TEXT:', (await page.locator('body').innerText()).slice(0, 200).replace(/\n/g,' | '));

await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
console.log('COMMENT TEXTAREAS:', JSON.stringify(await page.locator('textarea').evaluateAll(els=>els.map(e=>({name:e.name,placeholder:e.placeholder})))));
await browser.close();
