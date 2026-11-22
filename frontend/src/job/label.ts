import type { JobView } from '@/api/client';
import { readReport } from '@/report/read';

const SNIPPET_LENGTH = 140;

// A finished analysis is named after the start of its summary; anything still running
// (or without a summary) falls back to the first file name.
export function jobLabel(job: JobView | undefined): string {
  if (!job) {
    return 'Task';
  }
  if (job.status === 'succeeded') {
    const summary = readReport(job.report)?.headline.replace(/\s+/g, ' ').trim();
    if (summary) {
      return summary.length > SNIPPET_LENGTH
        ? `${summary.slice(0, SNIPPET_LENGTH).trimEnd()}…`
        : summary;
    }
  }
  return (
    job.documents[0]?.filename ??
    job.rejected_files[0]?.filename ??
    job.excluded_files[0]?.filename ??
    'Task'
  );
}

export function jobKey(id: string): readonly ['job', string] {
  return ['job', id];
}
