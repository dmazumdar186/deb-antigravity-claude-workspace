import { test, expect } from '@playwright/test';

test('home page renders and has skip-link', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/./);
  const skipLink = page.getByRole('link', { name: /skip to content/i });
  await expect(skipLink).toBeInViewport({ ratio: 0 }).catch(() => {});
  // Skip link should exist in DOM even if visually hidden.
  await expect(skipLink).toHaveCount(1);
});

test('main landmark exists', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('main')).toBeVisible();
});
