import { chromium } from '@playwright/test';
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const media = [];
page.on('response', r => { if (/\.(m3u8|mp4|ts)(\?|$)/.test(r.url())) media.push(`${r.status()} ${r.url()}`); });
await page.goto('http://localhost/view?m=juMSnf8VT', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(3000);
const info = await page.evaluate(() => {
  const v = document.querySelector('video');
  return {
    title: document.title,
    videos: document.querySelectorAll('video').length,
    videojs: !!document.querySelector('.video-js'),
    src: v ? (v.currentSrc || v.src) : null,
    readyState: v ? v.readyState : null,
    duration: v ? v.duration : null,
    paused: v ? v.paused : null,
    size: v ? `${v.videoWidth}x${v.videoHeight}` : null,
    text: (document.body.innerText || '').slice(0, 300)
  };
});
console.log(JSON.stringify(info, null, 2));
console.log('MEDIA RESPONSES:');
console.log(media.slice(0, 15).join('\n') || '(none)');
await page.screenshot({ path: 'probe-video.png', fullPage: false });
await browser.close();
