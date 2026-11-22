import { useRef, useState } from 'react';
import {
  ArrowRight,
  Check,
  CircleAlert,
  Clock,
  FileSearch,
  PenLine,
  Shield,
  Upload,
  X,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  addJobDocuments,
  ApiError,
  cancelJob,
  confirmJob,
  createJob,
  getJob,
  type JobView,
} from '@/api/client';
import { DropZone } from '@/upload/drop-zone';
import { checkFiles, type FileNotice } from '@/upload/files';

type View =
  | { kind: 'ready'; notices: FileNotice[] }
  | { kind: 'starting' }
  | { kind: 'progress'; job: JobView }
  | { kind: 'rejected'; job: JobView; notices: FileNotice[] };

const STATUS_LABEL: Record<string, string> = {
  pending: 'Queued',
  extracting: 'Extracting',
  checking: 'Checking',
  summarising: 'Summarising',
  succeeded: 'Done',
  failed: 'Failed',
};

const STATUS_ICON = {
  pending: Clock,
  extracting: FileSearch,
  checking: Shield,
  summarising: PenLine,
  succeeded: Check,
  failed: X,
};

function StatusIcon({ status }: { status: string }) {
  const Icon = STATUS_ICON[status as keyof typeof STATUS_ICON] ?? Clock;
  return <Icon className="size-4" aria-hidden />;
}

function noticeFrom(error: unknown): FileNotice {
  if (error instanceof ApiError) {
    return { filename: '', message: error.message };
  }
  return { filename: '', message: 'The upload failed.' };
}

function screenFor(job: JobView): View {
  if (job.status === 'awaiting_input' || job.rejected_files.length > 0) {
    return { kind: 'rejected', job, notices: [] };
  }
  return { kind: 'progress', job };
}

export function HomePage() {
  const [view, setView] = useState<View>({ kind: 'ready', notices: [] });
  const reuploadRef = useRef<HTMLInputElement>(null);

  async function startJob(files: File[]) {
    const checked = checkFiles(files);
    if (checked.notices.length > 0 || checked.accepted.length === 0) {
      setView({ kind: 'ready', notices: checked.notices });
      return;
    }
    setView({ kind: 'starting' });
    try {
      const created = await createJob(checked.accepted);
      setView(screenFor(await getJob(created.id)));
    } catch (error) {
      setView({ kind: 'ready', notices: [noticeFrom(error)] });
    }
  }

  async function reupload(files: File[]) {
    if (view.kind !== 'rejected') {
      return;
    }
    const checked = checkFiles(files);
    if (checked.notices.length > 0 || checked.accepted.length === 0) {
      setView({ ...view, notices: checked.notices });
      return;
    }
    const current = view.job;
    setView({ kind: 'starting' });
    try {
      setView(screenFor(await addJobDocuments(current.id, checked.accepted)));
    } catch (error) {
      setView({ kind: 'rejected', job: current, notices: [noticeFrom(error)] });
    }
  }

  async function continueWithout() {
    if (view.kind !== 'rejected') {
      return;
    }
    const current = view.job;
    setView({ kind: 'starting' });
    try {
      setView(screenFor(await confirmJob(current.id)));
    } catch (error) {
      setView({ kind: 'rejected', job: current, notices: [noticeFrom(error)] });
    }
  }

  async function cancel() {
    if (view.kind !== 'rejected') {
      return;
    }
    const current = view.job;
    setView({ kind: 'starting' });
    try {
      await cancelJob(current.id);
      setView({ kind: 'ready', notices: [{ filename: '', message: 'Cancelled.' }] });
    } catch (error) {
      setView({ kind: 'rejected', job: current, notices: [noticeFrom(error)] });
    }
  }

  const subtitle =
    view.kind === 'progress'
      ? 'Reading the files.'
      : view.kind === 'rejected'
        ? 'Some files were left out.'
        : view.kind === 'starting'
          ? 'Starting.'
          : 'Drop your PDFs. One report comes back.';

  const notices = view.kind === 'ready' || view.kind === 'rejected' ? view.notices : [];

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col items-center justify-center px-6 py-16 text-center">
      <h1 className="text-5xl font-medium tracking-tight text-balance sm:text-6xl">Doc Insight</h1>
      <p className="mt-4 max-w-xl text-lg text-muted-foreground">{subtitle}</p>

      {view.kind === 'ready' && <DropZone onFiles={(files) => void startJob(files)} />}

      {notices.length > 0 && (
        <ul className="mt-8 w-full space-y-2 text-left text-sm">
          {notices.map((notice) => (
            <li key={`${notice.filename}:${notice.message}`}>
              {notice.filename ? `${notice.filename}: ${notice.message}` : notice.message}
            </li>
          ))}
        </ul>
      )}

      {view.kind === 'progress' && (
        <ul className="mt-12 w-full space-y-3 text-left" aria-label="Files">
          {view.job.documents.map((document) => (
            <li key={document.id} className="flex items-baseline justify-between gap-6 text-base">
              <span>{document.filename}</span>
              <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                <StatusIcon status={document.status} />
                {STATUS_LABEL[document.status] ?? document.status}
              </span>
            </li>
          ))}
        </ul>
      )}

      {view.kind === 'rejected' && (
        <section className="mt-12 w-full text-left">
          <ul className="space-y-3">
            {view.job.documents.map((document) => (
              <li key={document.id}>{document.filename}</li>
            ))}
            {view.job.rejected_files.map((file) => (
              <li key={file.id}>
                <span>{file.filename}</span>
                <span className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                  <CircleAlert className="size-3.5" aria-hidden />
                  {file.message}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" onClick={() => reuploadRef.current?.click()}>
              <Upload data-icon="inline-start" />
              Re-upload
            </Button>
            <input
              ref={reuploadRef}
              aria-label="Re-upload"
              className="sr-only"
              type="file"
              accept="application/pdf,.pdf"
              multiple
              onChange={(event) => {
                const chosen = [...(event.target.files ?? [])];
                event.target.value = '';
                if (chosen.length > 0) {
                  void reupload(chosen);
                }
              }}
            />
            <Button type="button" onClick={() => void continueWithout()}>
              Continue without them
              <ArrowRight data-icon="inline-end" />
            </Button>
            <Button type="button" variant="ghost" onClick={() => void cancel()}>
              <X data-icon="inline-start" />
              Cancel
            </Button>
          </div>
        </section>
      )}
    </main>
  );
}
