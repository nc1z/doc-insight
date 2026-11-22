import { useQuery } from '@tanstack/react-query';

import { Card, CardContent, CardHeader } from '@/components/ui/card';

async function readHealth(): Promise<string> {
  const response = await fetch('/api/health');
  const status = `${response.status} ${response.statusText}`.trim();
  if (!response.ok) {
    throw new Error(status);
  }
  return status;
}

export function HomePage() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: readHealth,
  });

  return (
    <main className="mx-auto flex min-h-svh max-w-lg flex-col justify-center p-6">
      <Card>
        <CardHeader>
          <h1 className="font-heading text-3xl font-medium">Doc Insight</h1>
        </CardHeader>
        <CardContent>
          <p role="status">
            Backend health: {health.isPending && 'checking…'}
            {health.isSuccess && health.data}
            {health.isError &&
              `unavailable (${health.error instanceof Error ? health.error.message : 'Request failed'})`}
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
