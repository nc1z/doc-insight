import {
  Check,
  Clock,
  FileSearch,
  FileText,
  LoaderCircle,
  PenLine,
  RotateCcw,
  Shield,
  TriangleAlert,
  X,
} from 'lucide-react';

import type { JobView } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from 'cn';

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

const STATUS_TONE: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  extracting: 'bg-info/10 text-info',
  checking: 'bg-info/10 text-info',
  summarising: 'bg-info/10 text-info',
  succeeded: 'bg-success/10 text-success',
  failed: 'bg-destructive/10 text-destructive',
};

const FLAG_LABEL: Record<string, string> = {
  hidden_text: 'Hidden text',
  invisible_characters: 'Invisible characters',
  encoded_blob: 'Encoded text',
  classifier: 'Looks like an instruction',
};

const ACTIVE = new Set(['extracting', 'checking', 'summarising']);

function StatusBadge({ status }: { status: string }) {
  const Icon = STATUS_ICON[status as keyof typeof STATUS_ICON] ?? Clock;
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        STATUS_TONE[status] ?? STATUS_TONE.pending,
      )}
    >
      {ACTIVE.has(status) ? (
        <LoaderCircle className="size-3.5 animate-spin" aria-hidden />
      ) : (
        <Icon className="size-3.5" aria-hidden />
      )}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function progressPercent(job: JobView): number {
  if (job.progress.total_steps <= 0) {
    return 0;
  }
  return Math.round((job.progress.completed_steps / job.progress.total_steps) * 100);
}

export function FileList({
  job,
  onRetry,
  retrying,
}: {
  job: JobView;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const percent = progressPercent(job);
  return (
    <div className="w-full text-left">
      <div className="mb-5 flex items-center gap-4">
        <Progress value={percent} aria-label="Progress" />
        <span className="w-10 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
          {percent}%
        </span>
      </div>
      <ul
        className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-card"
        aria-label="Files"
      >
        {job.documents.map((document) => (
          <li key={document.id} className="px-4 py-3.5">
            <div className="flex items-center gap-3.5">
              <span
                aria-hidden
                className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-muted-foreground"
              >
                <FileText className="size-4" />
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium">
                {document.filename}
              </span>
              <StatusBadge status={document.status} />
              {document.status === 'failed' && onRetry && (
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  aria-label={`Retry ${document.filename}`}
                  disabled={retrying}
                  onClick={onRetry}
                >
                  <RotateCcw />
                </Button>
              )}
            </div>
            {document.error && (
              <p className="mt-2 pl-[3.125rem] text-[0.8125rem] leading-5 text-muted-foreground">
                {document.error.message}
              </p>
            )}
            {document.flagged && (
              <p className="mt-2 flex items-center gap-1.5 pl-[3.125rem] text-[0.8125rem] leading-5 text-warning">
                <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
                {document.flag_reasons.map((reason) => FLAG_LABEL[reason] ?? reason).join(', ')}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
