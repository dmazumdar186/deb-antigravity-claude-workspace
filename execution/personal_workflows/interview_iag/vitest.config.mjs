import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/unit/**/*.test.mjs', 'tests/integration/**/*.test.mjs'],
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
    testTimeout: 30_000,
  },
});
