import { expect, test } from '@playwright/test';

test('home page loads', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Doc Insight' })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Backend health: 200 OK');
});
