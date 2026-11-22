import { describe, expect, it } from 'vitest';

import { pollInterval } from '@/job/poll';
import { readReport, readSummary } from '@/report/read';
import { readJobIds, readSidebarOpen, writeJobIds, writeSidebarOpen } from '@/shell/storage';

describe('poll interval', () => {
  it('polls only while work is in progress', () => {
    expect(pollInterval('queued')).toBe(1500);
    expect(pollInterval('running')).toBe(1500);
    expect(pollInterval('consolidating')).toBe(1500);
    expect(pollInterval('awaiting_input')).toBe(false);
    expect(pollInterval('succeeded')).toBe(false);
    expect(pollInterval(undefined)).toBe(false);
    expect(pollInterval('running', 1)).toBe(3000);
    expect(pollInterval('running', 5)).toBe(30000);
  });
});

describe('sidebar storage', () => {
  it('keeps the sidebar open unless it was closed', () => {
    localStorage.clear();
    expect(readSidebarOpen()).toBe(true);
    writeSidebarOpen(false);
    expect(readSidebarOpen()).toBe(false);
    writeJobIds(['job-1', 'job-2']);
    expect(readJobIds()).toEqual(['job-1', 'job-2']);
  });
});

describe('report reader', () => {
  it('reads a summary and a report', () => {
    expect(
      readSummary({
        title: 'Desk note',
        inferred_type: 'letter',
        summary: 'A short note.',
        topics: ['mock'],
        notable_points: [{ text: 'Point', page: 1, quote: 'Words' }],
      })?.title,
    ).toBe('Desk note');
    expect(readReport({ summary: 'One report.', themes: ['mock'], takeaways: [] })?.summary).toBe(
      'One report.',
    );
    expect(readReport(null)).toBeNull();
  });
});
