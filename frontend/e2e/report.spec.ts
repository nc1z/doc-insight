import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

const deskNote = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../samples/desk-note.pdf',
);

const running = {
  id: 'job-report',
  status: 'queued',
  progress: { completed_steps: 1, total_steps: 3 },
  documents: [
    {
      id: 'doc-1',
      filename: 'desk-note.pdf',
      status: 'extracting',
      flagged: true,
      flag_reasons: ['hidden_text'],
      error: null,
      summary: null,
    },
  ],
  rejected_files: [],
  excluded_files: [],
  report: null,
  error: null,
};

const done = {
  ...running,
  status: 'succeeded',
  progress: { completed_steps: 3, total_steps: 3 },
  documents: [
    {
      ...running.documents[0],
      status: 'succeeded',
      summary: {
        title: 'Desk note',
        inferred_type: 'letter',
        summary: 'Mock summary of desk-note.pdf.',
        topics: ['mock'],
        entities: { people: [], organisations: [], locations: [], dates: [] },
        notable_points: [{ text: 'Mock point', page: 1, quote: 'A line from the note.' }],
      },
    },
  ],
  report: {
    summary: 'Mock report of desk-note.pdf.',
    themes: ['mock'],
    contradictions: [],
    entities: { people: [], organisations: [], locations: [], dates: [] },
    takeaways: ['Mock takeaway'],
    flagged_documents: ['desk-note.pdf'],
    excluded_files: [],
  },
};

test('a finished upload opens again from the sidebar', async ({ page }) => {
  const started = Date.now();
  await page.route(
    (url) => url.pathname === '/api/jobs',
    async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'job-report', status: 'queued' }),
      });
    },
  );
  await page.route('**/api/jobs/job-report', async (route) => {
    await route.fulfill({ json: Date.now() - started > 500 ? done : running });
  });

  await page.goto('/');
  await page.getByLabel('Upload documents').setInputFiles(deskNote);

  await expect(page.getByRole('heading', { name: 'Analysing your documents' })).toBeVisible();
  await expect(page.getByText('Hidden text')).toBeVisible();
  await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible();
  await expect(page.getByText('Mock report of desk-note.pdf.')).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'desk-note.pdf' }).click();
  await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible();
  await page.getByRole('tab', { name: 'desk-note.pdf' }).click();
  await expect(page.getByText('Mock summary of desk-note.pdf.')).toBeVisible();
  await expect(page.getByText('A line from the note.')).toBeVisible();
});
