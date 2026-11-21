import { useEffect, useState } from 'react';

type Health =
  { state: 'loading' } | { state: 'ok'; status: string } | { state: 'error'; message: string };

function App() {
  const [health, setHealth] = useState<Health>({ state: 'loading' });

  useEffect(() => {
    const controller = new AbortController();

    fetch('/api/health', { signal: controller.signal })
      .then((response) => {
        const status = `${response.status} ${response.statusText}`.trim();
        if (!response.ok) {
          throw new Error(status);
        }
        setHealth({ state: 'ok', status });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setHealth({
          state: 'error',
          message: error instanceof Error ? error.message : 'Request failed',
        });
      });

    return () => controller.abort();
  }, []);

  return (
    <main>
      <h1>Doc Insight</h1>
      <p role="status">
        Backend health: {health.state === 'loading' && 'checking…'}
        {health.state === 'ok' && health.status}
        {health.state === 'error' && `unavailable (${health.message})`}
      </p>
    </main>
  );
}

export default App;
