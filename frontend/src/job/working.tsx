import {
  Check,
  FileSearch,
  Layers,
  PenLine,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import type { JobView } from '@/api/client';
import { Progress } from '@/components/ui/progress';
import { FileList } from '@/job/files';
import { cn } from 'cn';

type StepState = 'done' | 'active' | 'todo';

const STEPS: {
  label: string;
  icon: LucideIcon;
  title: string;
  messages: string[];
}[] = [
  {
    label: 'Read',
    icon: FileSearch,
    title: 'Reading your files',
    messages: [
      'Extracting text from every page…',
      'Looking at images and scanned pages…',
      'Getting each document ready…',
    ],
  },
  {
    label: 'Check',
    icon: ShieldCheck,
    title: 'Running safety checks',
    messages: [
      'Scanning for hidden text…',
      'Checking for instructions aimed at the model…',
      'Making sure every file is safe to read…',
    ],
  },
  {
    label: 'Summarise',
    icon: PenLine,
    title: 'Summarising each document',
    messages: [
      'Finding the main topics…',
      'Picking out people, places and dates…',
      'Noting the key details and where they appear…',
    ],
  },
  {
    label: 'Consolidate',
    icon: Layers,
    title: 'Writing your consolidated report',
    messages: [
      'Reading the summaries side by side…',
      'Merging names and themes across documents…',
      'Drafting the overall summary…',
      'Polishing the final report…',
    ],
  },
];

// How far through the three per-document steps a file is (3 means finished).
function documentLevel(status: string): number {
  switch (status) {
    case 'checking':
      return 1;
    case 'summarising':
      return 2;
    case 'succeeded':
    case 'failed':
      return 3;
    default:
      return 0;
  }
}

// The steps follow what the file rows show. With several files in flight, every step that
// some file is on (or is still waiting on) pulses, so the card never disagrees with a row.
function stepStates(job: JobView): StepState[] {
  if (job.status === 'succeeded') {
    return ['done', 'done', 'done', 'done'];
  }
  if (job.status === 'consolidating') {
    return ['done', 'done', 'done', 'active'];
  }
  const levels = job.documents.map((document) => documentLevel(document.status));
  if (levels.length === 0) {
    return ['active', 'todo', 'todo', 'todo'];
  }
  const lowest = Math.min(...levels);
  if (lowest >= 3) {
    return ['done', 'done', 'done', 'active'];
  }
  const running = job.documents
    .filter((document) => document.status !== 'pending')
    .map((document) => documentLevel(document.status));
  const states = STEPS.map((_, index): StepState => {
    if (index < lowest) {
      return 'done';
    }
    if (index === 3) {
      return 'todo';
    }
    if (running.includes(index) || levels.some((level) => level > index)) {
      return 'active';
    }
    return 'todo';
  });
  if (!states.includes('active')) {
    states[lowest] = 'active';
  }
  return states;
}

// The backend counts the three per-document steps. The final report is one more step on top.
function overallPercent(job: JobView): number {
  const total = job.progress.total_steps + 1;
  if (job.status === 'succeeded') {
    return 100;
  }
  const percent = Math.round((job.progress.completed_steps / total) * 100);
  return Math.min(percent, 99);
}

function useCycle(length: number, ms: number): number {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (length <= 1) {
      return;
    }
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % length), ms);
    return () => window.clearInterval(timer);
  }, [length, ms]);
  return index;
}

function Stepper({ states }: { states: StepState[] }) {
  return (
    <ol className="flex items-start" aria-label="Steps">
      {STEPS.map((step, index) => {
        const state = states[index] ?? 'todo';
        const Icon = step.icon;
        return (
          <li
            key={step.label}
            aria-current={state === 'active' ? 'step' : undefined}
            className="relative flex flex-1 flex-col items-center gap-2 text-center"
          >
            {index > 0 && (
              <span aria-hidden className="absolute top-4 right-1/2 left-[-50%] h-px bg-border">
                <span
                  className={cn(
                    'block h-full origin-left bg-foreground transition-transform duration-700 ease-out',
                    state === 'todo' ? 'scale-x-0' : 'scale-x-100',
                  )}
                />
              </span>
            )}
            <span
              aria-hidden
              className={cn(
                'relative z-10 grid size-8 place-items-center rounded-full border transition-all duration-500',
                state === 'done' && 'border-foreground bg-foreground text-background',
                state === 'active' && 'border-foreground bg-card text-foreground shadow-card',
                state === 'todo' && 'border-border bg-card text-muted-foreground',
              )}
            >
              {state === 'done' ? (
                <Check className="size-4 animate-in zoom-in-50 duration-300" />
              ) : (
                <Icon className="size-4" />
              )}
              {state === 'active' && (
                <span className="absolute inset-0 animate-ping rounded-full border border-foreground/30" />
              )}
            </span>
            <span
              className={cn(
                'text-xs font-medium transition-colors duration-300',
                state === 'todo' ? 'text-muted-foreground' : 'text-foreground',
              )}
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Activity({
  active,
  finished,
  total,
}: {
  active: number;
  finished: number;
  total: number;
}) {
  const step = STEPS[active] ?? STEPS[0]!;
  const message = useCycle(step.messages.length, 2600);
  const Icon = active === STEPS.length - 1 ? Sparkles : step.icon;
  return (
    <div className="flex items-start gap-3.5" aria-live="polite">
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-foreground"
      >
        <Icon className="size-4 animate-pulse" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-4">
          <p className="text-sm font-medium">{step.title}</p>
          {active < STEPS.length - 1 && total > 0 && (
            <p className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {finished} of {total} {total === 1 ? 'file' : 'files'} done
            </p>
          )}
        </div>
        {/* Two lines reserved, so a longer message never pushes the page down. */}
        <div className="mt-0.5 min-h-10">
          <p
            key={`${active}:${message}`}
            className="animate-in text-sm leading-5 text-muted-foreground duration-500 fade-in-0 slide-in-from-bottom-1"
          >
            {step.messages[message % step.messages.length]}
          </p>
        </div>
      </div>
    </div>
  );
}

export function Working({ job }: { job: JobView }) {
  const states = stepStates(job);
  const active = Math.max(0, states.lastIndexOf('active'));
  const finished = job.documents.filter((document) => documentLevel(document.status) >= 3).length;
  const percent = overallPercent(job);
  const finalising = active === STEPS.length - 1;
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-border bg-card p-6 shadow-card">
        <Stepper states={states} />
        <div className="mt-6 flex items-center gap-4">
          <Progress
            value={percent}
            aria-label="Progress"
            className={cn(finalising && 'sheen-bar')}
          />
          <span className="w-10 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
            {percent}%
          </span>
        </div>
        <div className="mt-6 border-t border-border pt-6">
          <Activity active={active} finished={finished} total={job.documents.length} />
        </div>
      </div>
      <FileList job={job} showProgress={false} showSummaries />
    </div>
  );
}
