import { FileText, PanelLeftClose, SquarePen } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from 'cn';

export type HistoryItem = {
  id: string;
  label: string;
  status?: string;
};

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'grid size-7 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground shadow-[inset_0_1px_0_oklch(1_0_0/0.15)]',
        className,
      )}
    >
      <svg viewBox="0 0 16 16" className="size-3.5" fill="none">
        <path
          d="M4 2.75h5.2L12.25 5.8v7.45a.5.5 0 0 1-.5.5H4.25a.5.5 0 0 1-.5-.5V3.25a.5.5 0 0 1 .5-.5Z"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />
        <path
          d="M6 8.5h4M6 10.75h2.5"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

function StatusDot({ status }: { status?: string }) {
  if (!status) {
    return null;
  }
  const tone =
    status === 'succeeded'
      ? 'bg-success'
      : status === 'failed' || status === 'cancelled' || status === 'expired'
        ? 'bg-destructive'
        : status === 'awaiting_input'
          ? 'bg-warning'
          : 'bg-info animate-pulse';
  return <span aria-hidden className={cn('ml-auto size-1.5 shrink-0 rounded-full', tone)} />;
}

export function Sidebar({
  open,
  items,
  activeId,
  onToggle,
  onNewTask,
  onOpen,
}: {
  open: boolean;
  items: HistoryItem[];
  activeId: string | null;
  onToggle: () => void;
  onNewTask: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <>
      {/* In-flow spacer on desktop so the main column centres in the space that is left. */}
      <div
        aria-hidden
        className={cn(
          'hidden shrink-0 transition-[width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] md:block',
          open ? 'w-64' : 'w-0',
        )}
      />
      <div
        aria-hidden
        onClick={onToggle}
        className={cn(
          'fixed inset-0 z-30 bg-foreground/20 backdrop-blur-[2px] transition-opacity duration-300 md:hidden',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      />
      <aside
        id="sidebar"
        aria-hidden={!open}
        inert={!open}
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] max-md:shadow-2xl',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-14 shrink-0 items-center justify-between pr-2 pl-4">
          <div className="flex items-center gap-2.5">
            <BrandMark />
            <span className="text-[0.9375rem] font-semibold tracking-tight">Doc Insight</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Close sidebar"
            aria-expanded={open}
            aria-controls="sidebar"
            onClick={onToggle}
          >
            <PanelLeftClose />
          </Button>
        </div>

        <div className="px-3 pt-1 pb-2">
          <Button
            type="button"
            variant="outline"
            className="w-full justify-start gap-2 bg-card font-medium"
            onClick={onNewTask}
          >
            <SquarePen data-icon="inline-start" />
            New analysis
          </Button>
        </div>

        <nav aria-label="Recent analyses" className="flex-1 overflow-y-auto px-3 pt-3 pb-4">
          <p className="px-2 pb-2 text-xs font-medium tracking-wide text-muted-foreground">
            Recent
          </p>
          {items.length === 0 ? (
            <p className="px-2 text-[0.8125rem] leading-5 text-muted-foreground">
              Your analyses will show up here.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    aria-current={item.id === activeId ? 'page' : undefined}
                    className={cn(
                      'group flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm text-sidebar-foreground/80 transition-colors outline-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-ring/30',
                      item.id === activeId &&
                        'bg-sidebar-accent font-medium text-sidebar-accent-foreground',
                    )}
                    onClick={() => onOpen(item.id)}
                  >
                    <FileText aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 truncate">{item.label}</span>
                    <StatusDot status={item.status} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="border-t border-sidebar-border px-5 py-3.5">
          <p className="text-xs leading-5 text-muted-foreground">
            Recent analyses are kept in this browser.
          </p>
        </div>
      </aside>
    </>
  );
}
