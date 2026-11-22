import { useState } from 'react';
import { Upload } from 'lucide-react';

import { cn } from 'cn';

type DropZoneProps = {
  onFiles: (files: File[]) => void;
};

export function DropZone({ onFiles }: DropZoneProps) {
  const [over, setOver] = useState(false);

  return (
    <label
      className={cn(
        'mt-12 flex min-h-52 w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-white px-6 text-muted-foreground shadow-sm transition-colors',
        over && 'border-foreground text-foreground',
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
      <Upload className="size-8" strokeWidth={1.75} aria-hidden />
      <span className="text-base">Drop PDFs, or click to choose</span>
      <input
        aria-label="Upload PDFs"
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
