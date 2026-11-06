import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const controls = await page.evaluate(() => Array.from(document.querySelectorAll('.video-js [class*="vjs-"]'))
  .filter(e => e.className && typeof e.className === 'string')
  .map(e => e.className).filter(c => /control|button|menu|volume|fullscreen|subs|rate|quality|resolution/i.test(c)).slice(0, 40));
console.log('CONTROLS:', JSON.stringify([...new Set(controls)], null, 2));

await page.goto('http://localhost/', { waitUntil: 'networkidle' });
const nav = await page.evaluate(() => Array.from(document.querySelectorAll('a')).map(a => ({t:(a.innerText||'').trim(), h:a.getAttribute('href')})).filter(x => x.t && x.h).slice(0, 30));
console.log('NAV:', JSON.stringify(nav, null, 2));

for (const path of ['/search?q=Test', '/categories', '/login', '/upload']) {
  const resp = await page.goto('http://localhost' + path, { waitUntil: 'networkidle' }).catch(e => null);
  console.log('PAGE', path, 'status', resp ? resp.status() : 'ERR', 'url', page.url(), 'title', await page.title());
  console.log('  text:', (await page.locator('body').innerText()).slice(0, 160).replace(/\n/g, ' | '));
}
await browser.close();
