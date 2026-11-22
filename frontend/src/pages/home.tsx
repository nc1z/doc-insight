import { useQueryClient, useQueries } from '@tanstack/react-query';
import {
  ArrowRight,
  CircleAlert,
  FileText,
  GitCompare,
  LoaderCircle,
  PanelLeftOpen,
  ScanSearch,
  ShieldCheck,
  SquarePen,
  Upload,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useRef, useState, type RefObject } from 'react';

import {
  addJobDocuments,
  ApiError,
  cancelJob,
  confirmJob,
  createJob,
  getJob,
  retryJob,
  type JobView,
} from '@/api/client';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { FileList } from '@/job/files';
import { jobKey, jobLabel } from '@/job/label';
import { pollInterval } from '@/job/poll';
import { ReportView } from '@/report/view';
import { BrandMark, Sidebar } from '@/shell/sidebar';
import { readJobIds, readSidebarOpen, writeJobIds, writeSidebarOpen } from '@/shell/storage';
import { DropZone } from '@/upload/drop-zone';
import { checkFiles, type FileNotice } from '@/upload/files';
import { cn } from 'cn';

function noticeFrom(error: unknown): FileNotice {
  if (error instanceof ApiError && error.status === 0) {
    return {
      filename: '',
      message: "Can't reach the server. Check your connection and try again.",
    };
  }
  if (error instanceof ApiError) {
    return { filename: '', message: error.message };
  }
  return { filename: '', message: "The upload didn't go through. Please try again." };
}

function endedCopy(job: JobView): string {
  if (job.error?.message) {
    return job.error.message;
  }
  if (job.status === 'cancelled') {
    return 'This analysis was cancelled.';
  }
  if (job.status === 'expired') {
    return 'This analysis has expired.';
  }
  return 'Something went wrong while analysing these files.';
}

function isMobile(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 767px)').matches;
}

export function HomePage() {
  const queryClient = useQueryClient();
  const reuploadRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(() => readSidebarOpen() && !isMobile());
  const [ids, setIds] = useState(readJobIds);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [notices, setNotices] = useState<FileNotice[]>([]);
  const [missing, setMissing] = useState(false);
  const [held, setHeld] = useState<JobView | null>(null);
  const [busy, setBusy] = useState(false);

  const history = useQueries({
    queries: ids.map((id) => ({
      queryKey: jobKey(id),
      queryFn: () => getJob(id),
      refetchInterval: (query: { state: { data?: JobView } }) =>
        pollInterval(query.state.data?.status),
    })),
  });

  useEffect(() => {
    const drop: string[] = [];
    ids.forEach((id, index) => {
      const query = history[index];
      if (!query || query.isPending) {
        return;
      }
      const gone = query.error instanceof ApiError && query.error.status === 404;
      const expired = query.data?.status === 'expired';
      if (!gone && !expired) {
        return;
      }
      drop.push(id);
      if (id === activeId && gone) {
        setMissing(true);
      }
      if (id === activeId && expired && query.data) {
        setHeld(query.data);
      }
    });
    if (drop.length === 0) {
      return;
    }
    setIds((current) => {
      const next = current.filter((id) => !drop.includes(id));
      if (next.length === current.length) {
        return current;
      }
      writeJobIds(next);
      return next;
    });
  }, [activeId, history, ids]);

  function toggleSidebar() {
    setOpen((current) => {
      writeSidebarOpen(!current);
      return !current;
    });
  }

  function closeOnMobile() {
    if (isMobile()) {
      setOpen(false);
    }
  }

  function remember(id: string) {
    setIds((current) => {
      const next = [id, ...current.filter((item) => item !== id)];
      writeJobIds(next);
      return next;
    });
  }

  function showJob(next: JobView) {
    queryClient.setQueryData(jobKey(next.id), next);
    remember(next.id);
    setActiveId(next.id);
    setMissing(false);
    setHeld(null);
    setNotices([]);
  }

  function newTask() {
    setActiveId(null);
    setMissing(false);
    setHeld(null);
    setNotices([]);
    closeOnMobile();
  }

  async function startJob(files: File[]) {
    const checked = checkFiles(files);
    if (checked.notices.length > 0 || checked.accepted.length === 0) {
      setNotices(checked.notices);
      return;
    }
    setBusy(true);
    setNotices([]);
    try {
      const created = await createJob(checked.accepted);
      showJob(await getJob(created.id));
    } catch (error) {
      setNotices([noticeFrom(error)]);
    } finally {
      setBusy(false);
    }
  }

  async function reupload(files: File[]) {
    if (!activeId) {
      return;
    }
    const checked = checkFiles(files);
    if (checked.notices.length > 0 || checked.accepted.length === 0) {
      setNotices(checked.notices);
      return;
    }
    setBusy(true);
    try {
      showJob(await addJobDocuments(activeId, checked.accepted));
    } catch (error) {
      setNotices([noticeFrom(error)]);
    } finally {
      setBusy(false);
    }
  }

  async function continueWithout() {
    if (!activeId) {
      return;
    }
    setBusy(true);
    try {
      showJob(await confirmJob(activeId));
    } catch (error) {
      setNotices([noticeFrom(error)]);
    } finally {
      setBusy(false);
    }
  }

  async function retry() {
    if (!activeId) {
      return;
    }
    setBusy(true);
    try {
      showJob(await retryJob(activeId));
    } catch (error) {
      setNotices([noticeFrom(error)]);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!activeId) {
      return;
    }
    setBusy(true);
    try {
      const cancelled = await cancelJob(activeId);
      queryClient.setQueryData(jobKey(cancelled.id), cancelled);
      setActiveId(null);
      setNotices([{ filename: '', message: 'Cancelled.' }]);
    } catch (error) {
      setNotices([noticeFrom(error)]);
    } finally {
      setBusy(false);
    }
  }

  const activeIndex = activeId === null ? -1 : ids.indexOf(activeId);
  const activeQuery = activeIndex >= 0 ? history[activeIndex] : undefined;
  const job = activeQuery?.data;
  const unreachable =
    (activeQuery?.error instanceof ApiError && activeQuery.error.status === 0) ||
    history.some((query) => query.error instanceof ApiError && query.error.status === 0);

  const shown = job ?? (held && held.id === activeId ? held : undefined);
  const stage = stageFor(activeId, shown, missing, busy);
  const landing = stage === 'ready';
  const heading = headingFor(stage, shown);

  return (
    <div className="flex h-svh overflow-hidden bg-background">
      <Sidebar
        open={open}
        activeId={activeId}
        items={ids.map((id, index) => ({
          id,
          label: jobLabel(history[index]?.data),
          status: history[index]?.data?.status,
        }))}
        onToggle={toggleSidebar}
        onNewTask={newTask}
        onOpen={(id) => {
          setMissing(false);
          setHeld(null);
          setNotices([]);
          setActiveId(id);
          closeOnMobile();
        }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-1 px-3">
          {!open && (
            <>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Open sidebar"
                aria-expanded={open}
                aria-controls="sidebar"
                onClick={toggleSidebar}
              >
                <PanelLeftOpen />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="New analysis"
                onClick={newTask}
              >
                <SquarePen />
              </Button>
              <div className="ml-2 flex items-center gap-2.5">
                <BrandMark />
                <span className="text-[0.9375rem] font-semibold tracking-tight">Doc Insight</span>
              </div>
            </>
          )}
        </header>

        <div className="relative flex-1 overflow-y-auto">
          {landing && (
            <div
              aria-hidden
              className="hero-grid pointer-events-none absolute inset-x-0 top-0 h-112"
            />
          )}
          <main
            className={cn(
              'relative mx-auto flex min-h-full w-full max-w-3xl flex-col px-6 pb-16',
              landing || stage === 'ended' || stage === 'missing' ? 'justify-center' : 'pt-4',
            )}
          >
            {unreachable && (
              <Alert variant="destructive" className="mb-8">
                <CircleAlert />
                <AlertTitle>Can't reach the server</AlertTitle>
                <AlertDescription>Check that the API is running, then try again.</AlertDescription>
              </Alert>
            )}

            <div
              key={stage}
              className="animate-in fade-in-0 slide-in-from-bottom-2 duration-500 ease-out"
            >
              {landing && <Landing onFiles={(files) => void startJob(files)} notices={notices} />}

              {stage !== 'ready' && stage !== 'ended' && stage !== 'missing' && (
                <PageHeader title={heading.title} subtitle={heading.subtitle} />
              )}

              {stage === 'starting' && (
                <div className="mt-8 flex items-center gap-3 rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground shadow-card">
                  <LoaderCircle className="size-4 animate-spin" aria-hidden />
                  Uploading your files and getting started…
                </div>
              )}
              {stage === 'working' && shown && (
                <div className="mt-8">
                  <FileList job={shown} />
                </div>
              )}
              {stage === 'decision' && shown && (
                <Decision
                  job={shown}
                  notices={notices}
                  busy={busy}
                  reuploadRef={reuploadRef}
                  onReupload={(files) => void reupload(files)}
                  onContinue={() => void continueWithout()}
                  onCancel={() => void cancel()}
                  onRetry={() => void retry()}
                />
              )}
              {stage === 'report' && shown && (
                <div className="mt-8">
                  <ReportView job={shown} />
                </div>
              )}
              {stage === 'ended' && shown && <Ended message={endedCopy(shown)} onBack={newTask} />}
              {stage === 'missing' && (
                <Ended
                  message="We couldn't find that analysis. It may have been removed."
                  onBack={newTask}
                />
              )}

              {!landing && stage !== 'decision' && notices.length > 0 && (
                <Notices notices={notices} className="mt-8" />
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

type Stage = 'ready' | 'starting' | 'working' | 'decision' | 'report' | 'ended' | 'missing';

function stageFor(
  activeId: string | null,
  job: JobView | undefined,
  missing: boolean,
  busy: boolean,
): Stage {
  if (missing) {
    return 'missing';
  }
  if (!activeId) {
    return busy ? 'starting' : 'ready';
  }
  if (!job) {
    return 'starting';
  }
  if (job.status === 'failed' || job.status === 'cancelled' || job.status === 'expired') {
    return 'ended';
  }
  if (job.status === 'succeeded') {
    return 'report';
  }
  if (job.status === 'awaiting_input') {
    return 'decision';
  }
  return 'working';
}

function headingFor(stage: Stage, job: JobView | undefined): { title: string; subtitle: string } {
  switch (stage) {
    case 'starting':
      return { title: 'Uploading', subtitle: 'This only takes a moment.' };
    case 'working':
      return {
        title: 'Analysing your documents',
        subtitle: 'Reading each file and writing your report. This page updates on its own.',
      };
    case 'decision': {
      const rejected = (job?.rejected_files.length ?? 0) > 0;
      return {
        title: 'A few files need your attention',
        subtitle: rejected
          ? 'Some files were left out. Upload replacements, or continue with the rest.'
          : "A file couldn't be processed. Retry it, or continue without it.",
      };
    }
    case 'report': {
      const count = job?.documents.length ?? 0;
      return {
        title: 'Your report',
        subtitle: `${count} ${count === 1 ? 'document' : 'documents'} analysed.`,
      };
    }
    default:
      return { title: '', subtitle: '' };
  }
}

function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="text-left">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-[1.75rem]">{title}</h1>
      <p className="mt-1.5 text-muted-foreground">{subtitle}</p>
    </div>
  );
}

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: ScanSearch,
    title: 'Key details per document',
    body: 'Main topics, key entities and notable points, with the page each came from.',
  },
  {
    icon: GitCompare,
    title: 'Consolidated summary',
    body: 'One summary report that covers every document you upload.',
  },
  {
    icon: ShieldCheck,
    title: 'Safety checks',
    body: 'Flags hidden text and instruction-like content before it is read.',
  },
];

function Landing({
  onFiles,
  notices,
}: {
  onFiles: (files: File[]) => void;
  notices: FileNotice[];
}) {
  return (
    <>
      <div className="text-center">
        <h1 className="text-4xl leading-[1.1] font-semibold tracking-[-0.03em] sm:text-5xl">
          Turn documents into one clear report
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
          Upload one or more documents. Doc Insight pulls out the key details from each one and
          writes a consolidated summary across all of them.
        </p>
      </div>
      <div className="mt-10">
        <DropZone onFiles={onFiles} />
      </div>
      {notices.length > 0 && <Notices notices={notices} className="mt-4" />}
      <ul className="mt-10 grid divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <li key={title} className="p-5">
            <Icon className="size-4 text-muted-foreground" aria-hidden />
            <p className="mt-3 text-sm font-medium">{title}</p>
            <p className="mt-1 text-[0.8125rem] leading-5 text-muted-foreground">{body}</p>
          </li>
        ))}
      </ul>
    </>
  );
}

function Notices({ notices, className }: { notices: FileNotice[]; className?: string }) {
  return (
    <Alert variant="warning" className={className}>
      <CircleAlert />
      <AlertDescription className="text-foreground">
        <ul className="space-y-1">
          {notices.map((notice) => (
            <li key={`${notice.filename}:${notice.message}`}>
              {notice.filename ? `${notice.filename}: ${notice.message}` : notice.message}
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

function Ended({ message, onBack }: { message: string; onBack: () => void }) {
  return (
    <div className="flex flex-col items-center py-24 text-center">
      <span
        aria-hidden
        className="grid size-12 place-items-center rounded-xl border border-border bg-secondary text-muted-foreground"
      >
        <FileText className="size-5" strokeWidth={1.6} />
      </span>
      <p className="mt-5 max-w-sm text-lg font-medium tracking-tight text-balance">{message}</p>
      <Button type="button" variant="outline" className="mt-6" onClick={onBack}>
        <SquarePen data-icon="inline-start" />
        Start a new analysis
      </Button>
    </div>
  );
}

function Decision({
  job,
  notices,
  busy,
  reuploadRef,
  onReupload,
  onContinue,
  onCancel,
  onRetry,
}: {
  job: JobView;
  notices: FileNotice[];
  busy: boolean;
  reuploadRef: RefObject<HTMLInputElement | null>;
  onReupload: (files: File[]) => void;
  onContinue: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const failed = job.documents.some((document) => document.status === 'failed');
  return (
    <section className="mt-8 w-full text-left">
      <FileList job={job} onRetry={failed ? onRetry : undefined} retrying={busy} />
      {job.rejected_files.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Left out
          </h2>
          <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-card">
            {job.rejected_files.map((file) => (
              <li key={file.id} className="px-4 py-3.5">
                <span className="text-sm font-medium">{file.filename}</span>
                <span className="mt-1 flex items-center gap-1.5 text-[0.8125rem] text-warning">
                  <CircleAlert className="size-3.5 shrink-0" aria-hidden />
                  {file.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {notices.length > 0 && <Notices notices={notices} className="mt-6" />}
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button type="button" onClick={onContinue}>
          Continue without them
          <ArrowRight data-icon="inline-end" />
        </Button>
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
              onReupload(chosen);
            }
          }}
        />
        <Button type="button" variant="ghost" className="sm:ml-auto" onClick={onCancel}>
          <X data-icon="inline-start" />
          Cancel
        </Button>
      </div>
    </section>
  );
}
