import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { HomePage } from '@/pages/home';
import { createQueryClient } from '@/query';

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <HomePage />
    </QueryClientProvider>,
  );
}

describe('home page', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows the backend health status on load', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok' }), { status: 200, statusText: 'OK' }),
      );
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    expect(await screen.findByText('Backend health: 200 OK')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/health');
  });

  it('shows an error when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')));

    renderPage();

    expect(await screen.findByText(/unavailable \(Failed to fetch\)/)).toBeInTheDocument();
  });
});
