const ACTIVE = new Set(['queued', 'running', 'consolidating']);

export function pollInterval(status: string | undefined): number | false {
  return status !== undefined && ACTIVE.has(status) ? 1500 : false;
}
