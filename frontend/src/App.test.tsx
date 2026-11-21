import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

describe('App', () => {
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

    render(<App />);

    expect(await screen.findByRole('status')).toHaveTextContent('Backend health: 200 OK');
    expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.anything());
  });

  it('shows an error when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')));

    render(<App />);

    expect(await screen.findByText(/unavailable \(Failed to fetch\)/)).toBeInTheDocument();
  });
});
