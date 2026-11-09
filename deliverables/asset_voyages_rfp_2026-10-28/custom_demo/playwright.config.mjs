// Run: BASE_URL=http://localhost:8787 npx playwright test   (or the deployed URL)
import { defineConfig } from 'playwright/test';
import { readFileSync, existsSync } from 'node:fs';

// Test-run key (exempts the suite from the per-IP daily sandbox cap): env first, else the gitignored .dev.vars.
const devVars = existsSync(new URL('./.dev.vars', import.meta.url)) ? readFileSync(new URL('./.dev.vars', import.meta.url), 'utf8') : '';
export const TEST_KEY = process.env.DEMO_TEST_KEY || (/^DEMO_TEST_KEY=(.+)$/m.exec(devVars) || [])[1] || '';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8787';
export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: `test-results/results-${BASE_URL.includes('localhost') ? 'local' : 'live'}.json` }]],
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    extraHTTPHeaders: TEST_KEY ? { 'x-demo-test': TEST_KEY } : {},
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: 'off',
    screenshot: 'off',
  },
});
