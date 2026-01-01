import { test, expect } from '@playwright/test';

test.describe('Smoke Tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByTestId('app-title')).toBeVisible();
    await expect(page.getByTestId('welcome-message')).toBeVisible();
  });
});
