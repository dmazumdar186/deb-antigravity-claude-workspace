import { defineConfig } from '@playwright/test';

// Base Playwright config. Runs against a local `astro preview` by default,
// but honors PLAYWRIGHT_BASE_URL for CI runs against a preview deploy.
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: true,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4321',
    trace: 'on-first-retry',
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: 'npm run preview',
        port: 4321,
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
