const ACTIVE = new Set(['queued', 'running', 'consolidating']);

function configuredInterval(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const baseInterval = configuredInterval(import.meta.env.VITE_POLL_INTERVAL_MS, 1500);
const maxInterval = configuredInterval(import.meta.env.VITE_POLL_MAX_INTERVAL_MS, 30_000);

export function pollInterval(status: string | undefined, failures = 0): number | false {
  if (status === undefined || !ACTIVE.has(status)) {
    return false;
  }
  if (failures <= 0) {
    return baseInterval;
  }
  return Math.min(maxInterval, baseInterval * 2 ** Math.min(failures, 5));
}
