import { expect, test } from '@playwright/test';

test('home page loads', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByRole('heading', { name: 'Turn documents into one clear report' }),
  ).toBeVisible();
  await expect(page.getByText('Drop documents here, or click to browse')).toBeVisible();
  await expect(page.getByLabel('Upload documents')).toBeAttached();
  await expect(page.getByRole('button', { name: 'New analysis' })).toBeVisible();

  await page.getByRole('button', { name: 'Close sidebar' }).click();
  await expect(page.getByRole('button', { name: 'Open sidebar' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Open sidebar' })).toBeVisible();
});
