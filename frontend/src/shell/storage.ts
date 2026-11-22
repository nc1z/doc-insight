const SIDEBAR_KEY = 'doc-insight.sidebar';
const JOBS_KEY = 'doc-insight.jobs';

export function readSidebarOpen(): boolean {
  return localStorage.getItem(SIDEBAR_KEY) !== 'closed';
}

export function writeSidebarOpen(open: boolean): void {
  localStorage.setItem(SIDEBAR_KEY, open ? 'open' : 'closed');
}

export function readJobIds(): string[] {
  const raw = localStorage.getItem(JOBS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : [];
  } catch {
    return [];
  }
}

export function writeJobIds(ids: string[]): void {
  localStorage.setItem(JOBS_KEY, JSON.stringify(ids));
}
