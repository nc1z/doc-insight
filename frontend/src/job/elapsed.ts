import { useEffect, useMemo, useState } from 'react';

const KEY = 'doc-insight:started:';

// "0:07", "3:42", "1:02:09"
export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const seconds = String(total % 60).padStart(2, '0');
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}`
    : `${minutes}:${seconds}`;
}

// The API sends no timestamps, so the browser remembers when it first saw the job running.
// Session storage keeps the clock going through a refresh.
function startedAt(id: string): number {
  try {
    const saved = Number(sessionStorage.getItem(KEY + id));
    if (saved > 0) {
      return saved;
    }
    const now = Date.now();
    sessionStorage.setItem(KEY + id, String(now));
    return now;
  } catch {
    return Date.now();
  }
}

export function useElapsed(id: string): string {
  const start = useMemo(() => startedAt(id), [id]);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return formatElapsed(now - start);
}
