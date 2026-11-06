import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost/accounts/login/', { waitUntil: 'networkidle' });
await page.locator('#id_login').fill('admin');
await page.locator('#id_password').fill('MediaCMS@123');
await page.getByRole('button', { name: 'Sign In' }).click();
await page.waitForLoadState('networkidle');

await page.goto('http://localhost/upload', { waitUntil: 'networkidle' });
await page.locator('input[name="qqfile"]').setInputFiles('/tmp/sample.mp4');
await page.waitForTimeout(4000);
console.log('UPLOAD URL:', page.url());
console.log('UPLOAD TEXT:', (await page.locator('body').innerText()).slice(-600).replace(/\n/g,' | '));
console.log('UPLOAD INPUTS:', JSON.stringify(await page.evaluate(() => Array.from(document.querySelectorAll('input,textarea')).map(i=>({tag:i.tagName,name:i.name,type:i.type,placeholder:i.placeholder,value:i.value})))));

await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(800);
console.log('COMMENT BUTTONS:', JSON.stringify(await page.locator('button').evaluateAll(els=>els.map(e=>({t:(e.innerText||'').trim(),c:e.className})).filter(x=>x.t).slice(-10))));
await browser.close();
