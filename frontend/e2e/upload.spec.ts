import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

const samples = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../samples');
const deskNote = path.join(samples, 'desk-note.pdf');
const notes = path.join(samples, 'invalid/notes.pdf');

test('a valid upload shows each file', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Upload PDFs').setInputFiles(deskNote);

  await expect(page.getByText('Reading the files.')).toBeVisible();
  await expect(page.getByText('desk-note.pdf')).toBeVisible();
  await expect(page.getByLabel('Upload PDFs')).toHaveCount(0);
});

test('a mixed upload can continue, re-upload, or cancel', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Upload PDFs').setInputFiles([deskNote, notes]);

  await expect(page.getByText('notes.pdf')).toBeVisible();
  await expect(page.getByText('The file is not a PDF.')).toBeVisible();

  await page.getByRole('button', { name: 'Continue without them' }).click();
  await expect(page.getByText('Reading the files.')).toBeVisible();
  await expect(page.getByText('desk-note.pdf')).toBeVisible();
});

test('re-upload adds a file and cancel returns to the drop zone', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Upload PDFs').setInputFiles([deskNote, notes]);
  await expect(page.getByText('The file is not a PDF.')).toBeVisible();

  await page.getByLabel('Re-upload').setInputFiles(path.join(samples, 'broker-flash.pdf'));
  await expect(page.getByText('broker-flash.pdf')).toBeVisible();
  await expect(page.getByText('The file is not a PDF.')).toBeVisible();

  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByText('Cancelled.')).toBeVisible();
  await expect(page.getByLabel('Upload PDFs')).toBeVisible();
});
