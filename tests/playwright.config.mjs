import { defineConfig } from '@playwright/test';

const baseURL = process.env.BASE_URL || 'http://localhost';
const channel = process.env.PW_CHANNEL || 'chrome';

export default defineConfig({
  testDir: './specs',
  timeout: 45000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }], ['junit', { outputFile: 'results.xml' }]],
  use: {
    baseURL,
    headless: true,
    channel,
    launchOptions: { args: ['--no-sandbox'] },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
  },
});
