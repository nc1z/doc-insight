import type { JobView } from '@/api/client';

export function jobLabel(job: JobView | undefined): string {
  if (!job) {
    return 'Task';
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
