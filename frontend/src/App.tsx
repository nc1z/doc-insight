import { QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

import { HomePage } from '@/pages/home';
import { createQueryClient } from '@/query';

export default function App() {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <HomePage />
    </QueryClientProvider>
  );
}
