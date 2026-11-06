import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost/', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
console.log('HOME:', JSON.stringify({
  title: await page.title(),
  links: await page.locator('a[href*="/view?m="]').count(),
  text: (await page.locator('body').innerText()).slice(0, 400)
}, null, 2));
await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
console.log('VIDEO:', JSON.stringify({
  bigPlay: await page.locator('.vjs-big-play-button').isVisible().catch(()=>false),
  playControl: await page.locator('.vjs-play-control').isVisible().catch(()=>false),
  playControlCount: await page.locator('.vjs-play-control').count(),
  paused: await page.locator('video').evaluate(v=>v.paused),
  muted: await page.locator('video').evaluate(v=>v.muted)
}, null, 2));
// try JS play
const playResult = await page.locator('video').evaluate(async v => { v.muted = true; try { await v.play(); return {ok:true, time:v.currentTime}; } catch(e) { return {ok:false, err:String(e)}; } });
await page.waitForTimeout(1200);
console.log('PLAY:', JSON.stringify({playResult, time: await page.locator('video').evaluate(v=>v.currentTime), paused: await page.locator('video').evaluate(v=>v.paused)}, null, 2));
await browser.close();
