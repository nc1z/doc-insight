import { Ellipsis, FileText, PanelLeftClose, SquarePen, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  return <span aria-hidden className={cn('mt-[7px] size-1.5 shrink-0 rounded-full', tone)} />;
}

export function Sidebar({
  open,
  items,
  activeId,
  onToggle,
  onNewTask,
  onOpen,
  onDelete,
  onClearAll,
}: {
  open: boolean;
  items: HistoryItem[];
  activeId: string | null;
  onToggle: () => void;
  onNewTask: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
}) {
  const [confirmingClear, setConfirmingClear] = useState(false);
  // Captured when the dialog opens, so the text doesn't change while it fades out.
  const [clearCount, setClearCount] = useState(0);
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
                <li key={item.id} className="group/item relative">
                  <button
                    type="button"
                    aria-current={item.id === activeId ? 'page' : undefined}
                    className={cn(
                      'flex w-full cursor-pointer items-start gap-2.5 rounded-lg py-2 pr-9 pl-2.5 text-left text-sm leading-5 text-sidebar-foreground/80 transition-colors outline-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-ring/30',
                      item.id === activeId &&
                        'bg-sidebar-accent font-medium text-sidebar-accent-foreground',
                    )}
                    onClick={() => onOpen(item.id)}
                  >
                    <FileText
                      aria-hidden
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                    />
                    <span className="line-clamp-2 min-w-0 flex-1 break-words">{item.label}</span>
                  </button>
                  <span className="pointer-events-none absolute top-0 right-0 flex h-9 w-9 items-center justify-center group-focus-within/item:opacity-0 group-hover/item:opacity-0 [@media(hover:none)]:hidden">
                    <StatusDot status={item.status} />
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Analysis options"
                        className="absolute top-1 right-1 size-7 text-muted-foreground opacity-0 transition-opacity group-focus-within/item:opacity-100 group-hover/item:opacity-100 data-[state=open]:bg-sidebar-accent data-[state=open]:opacity-100 data-[state=open]:text-foreground hover:bg-background/70 [@media(hover:none)]:opacity-100"
                      >
                        <Ellipsis />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem variant="destructive" onSelect={() => onDelete(item.id)}>
                        <Trash2 />
                        Remove from history
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="space-y-2 border-t border-sidebar-border px-3 py-3">
          {items.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-muted-foreground hover:text-destructive"
              onClick={() => {
                setClearCount(items.length);
                setConfirmingClear(true);
              }}
            >
              <Trash2 data-icon="inline-start" />
              Clear all
            </Button>
          )}
          <p className="px-2.5 text-xs leading-5 text-muted-foreground">
            Recent analyses are kept in this browser.
          </p>
        </div>
      </aside>
      <Dialog open={confirmingClear} onOpenChange={setConfirmingClear}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold tracking-tight">
              Clear all recent analyses?
            </DialogTitle>
            <DialogDescription>
              This removes {clearCount === 1 ? 'the analysis' : `all ${clearCount} analyses`} from
              this browser. You won&apos;t be able to reopen {clearCount === 1 ? 'it' : 'them'} from
              here.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmingClear(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => {
                setConfirmingClear(false);
                onClearAll();
              }}
            >
              Clear all
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
