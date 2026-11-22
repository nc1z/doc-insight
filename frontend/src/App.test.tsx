import { QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { HomePage } from '@/pages/home';
import { createQueryClient } from '@/query';

function renderHome() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <HomePage />
    </QueryClientProvider>,
  );
}

const queuedJob = {
  id: 'job-1',
  status: 'queued',
  progress: { completed_steps: 0, total_steps: 3 },
  documents: [
    {
      id: 'doc-1',
      filename: 'desk-note.pdf',
      status: 'pending',
      flagged: false,
      flag_reasons: [],
      error: null,
      summary: null,
    },
  ],
  rejected_files: [],
  excluded_files: [],
  report: null,
  error: null,
};

describe('home page', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('keeps an unsupported file on the page', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderHome();

    fireEvent.change(screen.getByLabelText('Upload documents'), {
      target: { files: [new File(['hello'], 'notes.txt', { type: 'text/plain' })] },
    });

    expect(
      await screen.findByText("notes.txt: This file type isn't supported."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('starts a job when the dropped files are supported', async () => {
    const fetchMock = vi.fn((_: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve(Response.json({ id: 'job-1', status: 'queued' }, { status: 202 }));
      }
      return Promise.resolve(Response.json(queuedJob));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderHome();

    fireEvent.change(screen.getByLabelText('Upload documents'), {
      target: { files: [new File(['%PDF'], 'desk-note.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findAllByText('desk-note.pdf')).toHaveLength(2);
    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.queryByLabelText('Upload documents')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/jobs',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(JSON.parse(localStorage.getItem('doc-insight.jobs') ?? '[]')).toEqual(['job-1']);
  });

  it('remembers when the sidebar is closed', () => {
    renderHome();

    fireEvent.click(screen.getByRole('button', { name: 'Close sidebar' }));

    expect(screen.getByRole('button', { name: 'Open sidebar' })).toBeInTheDocument();
    expect(localStorage.getItem('doc-insight.sidebar')).toBe('closed');
  });

  it('drops a missing task and says it was not found', async () => {
    localStorage.setItem('doc-insight.jobs', JSON.stringify(['missing']));
    let respond: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            respond = resolve;
          }),
      ),
    );
    renderHome();

    fireEvent.click(await screen.findByRole('button', { name: 'Task' }));
    respond(
      Response.json({ code: 'not_found', message: 'The job was not found.' }, { status: 404 }),
    );

    expect(
      await screen.findByText("We couldn't find that analysis. It may have been removed."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem('doc-insight.jobs') ?? '[]')).toEqual([]);
    });
  });
});
