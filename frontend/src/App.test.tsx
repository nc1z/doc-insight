import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { HomePage } from '@/pages/home';

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
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps a file that is not a PDF on the page', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    render(<HomePage />);

    fireEvent.change(screen.getByLabelText('Upload PDFs'), {
      target: { files: [new File(['hello'], 'notes.txt', { type: 'text/plain' })] },
    });

    expect(await screen.findByText('notes.txt: The file is not a PDF.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('starts a job when the dropped files are PDFs', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ id: 'job-1', status: 'queued' }, { status: 202 }))
      .mockResolvedValueOnce(Response.json(queuedJob));
    vi.stubGlobal('fetch', fetchMock);
    render(<HomePage />);

    fireEvent.change(screen.getByLabelText('Upload PDFs'), {
      target: { files: [new File(['%PDF'], 'desk-note.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findByText('desk-note.pdf')).toBeInTheDocument();
    expect(screen.getByText('Queued')).toBeInTheDocument();
    expect(screen.queryByLabelText('Upload PDFs')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/jobs',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
