import { useState } from 'react';
import { FileUp } from 'lucide-react';

import { cn } from 'cn';

import { MAX_FILE_BYTES, MAX_FILE_COUNT } from './files';

type DropZoneProps = {
  onFiles: (files: File[]) => void;
};

const MAX_MB = Math.round(MAX_FILE_BYTES / (1024 * 1024));

export function DropZone({ onFiles }: DropZoneProps) {
  const [over, setOver] = useState(false);

  return (
    <label
      className={cn(
        'group relative flex w-full cursor-pointer flex-col items-center justify-center gap-5 rounded-2xl border border-dashed border-input bg-card/80 px-6 py-12 text-center shadow-card transition-all duration-200 focus-within:ring-3 focus-within:ring-ring/25 hover:border-foreground/25 hover:bg-card hover:shadow-card-hover',
        over && 'border-foreground/40 bg-card shadow-card-hover ring-4 ring-ring/10',
      )}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        const dropped = [...event.dataTransfer.files];
        if (dropped.length > 0) {
          onFiles(dropped);
        }
      }}
    >
      <span
        aria-hidden
        className={cn(
          'grid size-12 place-items-center rounded-xl border border-border bg-secondary text-muted-foreground transition-all duration-200 group-hover:-translate-y-0.5 group-hover:text-foreground',
          over && '-translate-y-1 text-foreground',
        )}
      >
        <FileUp className="size-5" strokeWidth={1.6} />
      </span>
      <span className="space-y-1.5">
        <span className="block text-base font-medium tracking-tight">
          {over ? 'Release to upload' : 'Drop documents here, or click to browse'}
        </span>
        <span className="block text-sm text-muted-foreground">
          Up to {MAX_FILE_COUNT} files, {MAX_MB} MB each
        </span>
      </span>
      <input
        aria-label="Upload documents"
        className="sr-only"
        type="file"
        accept="application/pdf,.pdf"
        multiple
        onChange={(event) => {
          const chosen = [...(event.target.files ?? [])];
          event.target.value = '';
          if (chosen.length > 0) {
            onFiles(chosen);
          }
        }}
      />
    </label>
  );
}
