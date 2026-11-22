import type { components } from './schema';

export type ErrorBody = components['schemas']['ErrorBody'];
export type JobView = components['schemas']['JobView'];
export type QueuedJob = components['schemas']['QueuedJob'];
export type AwaitingJob = components['schemas']['AwaitingJob'];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? null;
  }
}

const root = '/api';

function isErrorBody(value: unknown): value is ErrorBody {
  if (typeof value !== 'object' || value === null) {
    return false;
  }
  const body = value as Record<string, unknown>;
  return typeof body.code === 'string' && typeof body.message === 'string';
}

async function readError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (isErrorBody(payload)) {
    return new ApiError(response.status, payload);
  }
  return new ApiError(response.status, {
    code: 'http_error',
    message: `${response.status} ${response.statusText}`.trim(),
  });
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${root}${path}`, init);
  } catch (error) {
    throw new ApiError(0, {
      code: 'unavailable',
      message: error instanceof Error ? error.message : 'Request failed',
    });
  }
  if (!response.ok) {
    throw await readError(response);
  }
  return response;
}

function form(files: File[]): FormData {
  const body = new FormData();
  for (const file of files) {
    body.append('files', file);
  }
  return body;
}

export function reportPdfUrl(id: string): string {
  return `${root}/jobs/${id}/report.pdf`;
}

export function getJob(id: string): Promise<JobView> {
  return request(`/jobs/${id}`).then((response) => response.json() as Promise<JobView>);
}

export function createJob(files: File[]): Promise<QueuedJob | AwaitingJob> {
  return request('/jobs', { method: 'POST', body: form(files) }).then(async (response) => {
    if (response.status === 201) {
      return response.json() as Promise<AwaitingJob>;
    }
    return response.json() as Promise<QueuedJob>;
  });
}

export function addJobDocuments(id: string, files: File[]): Promise<JobView> {
  return request(`/jobs/${id}/documents`, { method: 'POST', body: form(files) }).then(
    (response) => response.json() as Promise<JobView>,
  );
}

export function confirmJob(id: string): Promise<JobView> {
  return request(`/jobs/${id}/confirm`, { method: 'POST' }).then(
    (response) => response.json() as Promise<JobView>,
  );
}

export function retryJob(id: string): Promise<JobView> {
  return request(`/jobs/${id}/retry`, { method: 'POST' }).then(
    (response) => response.json() as Promise<JobView>,
  );
}

export function cancelJob(id: string): Promise<JobView> {
  return request(`/jobs/${id}/cancel`, { method: 'POST' }).then(
    (response) => response.json() as Promise<JobView>,
  );
}
