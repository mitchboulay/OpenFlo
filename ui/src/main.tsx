import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router';
import { createQueryClient } from '@/api/queryClient';
import { App } from './App';
import './styles/index.css';

const root = document.getElementById('root');
if (!root) throw new Error('index.html is missing #root');

/** `VITE_MSW=1 npm run dev` swaps the backend for the in-browser fake; production builds drop this. */
async function startDevMocks(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_MSW !== '1') return;
  const { startMockBackend } = await import('@/dev/mockBackend');
  await startMockBackend();
}

void startDevMocks().then(() =>
  createRoot(root).render(
    <StrictMode>
      <QueryClientProvider client={createQueryClient()}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  ),
);
