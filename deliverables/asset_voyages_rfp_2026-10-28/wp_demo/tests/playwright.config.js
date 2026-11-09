// Playwright config: one worker, files run in name order against the local Playground (port 9400).
const { defineConfig } = require('playwright/test');

module.exports = defineConfig({
	testDir: __dirname,
	// The screenshot run is separate (fresh seed): SHOTS=1 selects screens.spec.js only.
	testMatch: process.env.SHOTS ? /(^|[\\/])screens\.spec\.js$/ : /(^|[\\/])\d\d-[^\\/]*\.spec\.js$/,
	workers: 1,
	fullyParallel: false,
	timeout: 180000,
	expect: { timeout: 20000 },
	retries: 0,
	reporter: [['list'], ['json', { outputFile: `../.tmp/results-port${process.env.WP_PORT || '9400'}.json` }]],
	outputDir: `../.tmp/test-output-${process.env.WP_PORT || '9400'}`,
	use: {
		baseURL: process.env.WP_BASE || 'http://127.0.0.1:9400',
		locale: 'fr-FR',
		timezoneId: 'Europe/Paris',
		launchOptions: { args: ['--lang=fr-FR'], env: { ...process.env, LANG: 'fr_FR.UTF-8', LANGUAGE: 'fr_FR:fr', LC_ALL: 'fr_FR.UTF-8' } },
		deviceScaleFactor: 1,
		viewport: { width: 1440, height: 900 },
		navigationTimeout: 60000,
		actionTimeout: 30000,
	},
});
