import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, cancelJob, confirmJob, createJob, getJob, retryJob } from './client';

const job = {
  id: 'job-1',
  status: 'queued',
  progress: { completed_steps: 0, total_steps: 3 },
  documents: [],
  rejected_files: [],
  excluded_files: [],
  report: null,
  error: null,
};

describe('job client', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reads a job', async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(job));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getJob('job-1')).resolves.toEqual(job);
    expect(fetchMock).toHaveBeenCalledWith('/api/jobs/job-1', undefined);
  });

  it('turns an error body into one client error', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: 'not_found', message: 'The job was not found.', details: null },
            { status: 404 },
          ),
        ),
    );

    const error = await getJob('missing').catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 404,
      code: 'not_found',
      message: 'The job was not found.',
      details: null,
    });
  });

  it('turns a network failure into the same error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')));

    const error = await getJob('job-1').catch((caught: unknown) => caught);

    expect(error).toMatchObject({ status: 0, code: 'unavailable', message: 'Failed to fetch' });
  });

  it('posts files and the job actions', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ id: 'job-1', status: 'queued' }, { status: 202 }))
      .mockResolvedValueOnce(Response.json(job, { status: 202 }))
      .mockResolvedValueOnce(Response.json(job, { status: 202 }))
      .mockResolvedValue(Response.json(job));
    vi.stubGlobal('fetch', fetchMock);
    const file = new File(['%PDF'], 'desk-note.pdf', { type: 'application/pdf' });

    await createJob([file]);
    await confirmJob('job-1');
    await retryJob('job-1');
    await cancelJob('job-1');

    expect(fetchMock.mock.calls.map((call) => [call[0], call[1]?.method])).toEqual([
      ['/api/jobs', 'POST'],
      ['/api/jobs/job-1/confirm', 'POST'],
      ['/api/jobs/job-1/retry', 'POST'],
      ['/api/jobs/job-1/cancel', 'POST'],
    ]);
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeInstanceOf(FormData);
  });
});
