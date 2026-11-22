import { expect, test } from '@playwright/test';

test('home page loads', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Doc Insight' })).toBeVisible();
  await expect(page.getByText('Drop your PDFs. One report comes back.')).toBeVisible();
  await expect(page.getByLabel('Upload PDFs')).toBeVisible();
});
