// The open analysis lives in the URL (/jobs/<id>) so a refresh, a shared link, or the
// back button lands on the same screen. There is no router library; the History API is enough.
const JOB_PATH = /^\/jobs\/([^/]+)\/?$/;

export function readRouteId(): string | null {
  const match = JOB_PATH.exec(window.location.pathname);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

export function routePath(id: string | null): string {
  return id ? `/jobs/${encodeURIComponent(id)}` : '/';
}

export function pushRoute(id: string | null): void {
  const path = routePath(id);
  if (window.location.pathname !== path) {
    window.history.pushState(null, '', path);
  }
}
