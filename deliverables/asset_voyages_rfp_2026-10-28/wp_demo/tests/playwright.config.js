// Playwright config: one worker, files run in name order against the local Playground (port 9400).
const { defineConfig } = require('playwright/test');

module.exports = defineConfig({
	testDir: __dirname,
	testMatch: /\d\d-.*\.spec\.js$/,
	workers: 1,
	fullyParallel: false,
	timeout: 180000,
	expect: { timeout: 20000 },
	retries: 0,
	reporter: [['list'], ['json', { outputFile: '../.tmp/results.json' }]],
	outputDir: '../.tmp/test-output',
	use: {
		baseURL: process.env.WP_BASE || 'http://127.0.0.1:9400',
		locale: 'fr-FR',
		deviceScaleFactor: 1,
		viewport: { width: 1440, height: 900 },
		navigationTimeout: 60000,
		actionTimeout: 30000,
	},
});
