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
    const summary = readSummary({
      title: 'Desk note',
      inferred_type: 'letter',
      summary: 'A short note.',
      key_points: ['One', 'Two'],
      sections: [
        {
          heading: 'Context',
          paragraphs: ['Some detail.'],
          quotes: [{ quote: 'Words', page: 1, document: 'note.pdf' }],
        },
      ],
      topics: ['mock'],
      notable_points: [{ text: 'Point', page: 1, quote: 'Words' }],
    });
    expect(summary?.title).toBe('Desk note');
    expect(summary?.headline).toBe('A short note.');
    expect(summary?.keyPoints).toEqual(['One', 'Two']);
    expect(summary?.sections[0]?.quotes).toEqual([
      { quote: 'Words', page: 1, document: 'note.pdf' },
    ]);

    const report = readReport({
      summary: 'One report.',
      themes: ['mock'],
      takeaways: ['A', 'B'],
      sections: [{ heading: 'Theme', paragraphs: ['Detail.'] }],
    });
    expect(report?.headline).toBe('One report.');
    expect(report?.keyPoints).toEqual(['A', 'B']);
    expect(report?.sections).toHaveLength(1);
    expect(readReport(null)).toBeNull();
  });

  it('splits an older long summary into a headline and reading', () => {
    const report = readReport({
      summary: 'Four notes cover one stock. The view is split.\n\nSecond paragraph here.',
      themes: [],
      takeaways: [],
    });
    expect(report?.headline).toBe('Four notes cover one stock.');
    expect(report?.sections).toEqual([
      {
        heading: 'Summary',
        paragraphs: ['The view is split. Second paragraph here.'],
        quotes: [],
      },
    ]);
  });

  it('shortens older long themes and headlines', () => {
    const long =
      'Four research documents dated 11 and 12 March 2026 cover Northline Semiconductor (ticker NTLN), a designer of power stages, and show a divided view.';
    const report = readReport({
      summary: long,
      themes: ['Channel checks: 15 percent Q3 order cut at the lead customer'],
      takeaways: [],
    });
    expect(report?.themes).toEqual(['Channel checks']);
    expect(report?.headline.length).toBeLessThan(long.length / 1.4);
  });

  it('spreads notable points between paragraphs when there are no pull quotes', () => {
    const summary = readSummary({
      summary: 'Short. One two. Three four. Five six.',
      notable_points: [{ text: 'First', page: 2, quote: 'a' }],
    });
    expect(summary?.sections[0]?.quotes).toEqual([{ quote: 'a', page: 2, document: '' }]);
  });

  it('falls back to notable points when an older summary has no key points', () => {
    const summary = readSummary({
      title: 'Note',
      inferred_type: 'letter',
      summary: 'Short.',
      topics: [],
      notable_points: [
        { text: 'First', page: 1, quote: 'a' },
        { text: 'Second', page: 1, quote: 'b' },
      ],
    });
    expect(summary?.keyPoints).toEqual(['First', 'Second']);
    expect(summary?.sections).toEqual([]);
  });
});
