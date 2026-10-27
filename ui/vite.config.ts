import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

const BACKEND = 'http://127.0.0.1:8099';

/** Dev server only: serves msw's worker script for `VITE_MSW=1`, so nothing mock-related reaches `dist/`. */
function mswWorker(): Plugin {
  const script = createRequire(import.meta.url).resolve('msw/mockServiceWorker.js');
  return {
    name: 'openflo-msw-worker',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/mockServiceWorker.js', (_request, response) => {
        response.setHeader('Content-Type', 'text/javascript');
        response.end(readFileSync(script));
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), mswWorker()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: {
      '/api': BACKEND,
      '/healthz': BACKEND,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    restoreMocks: true,
    // Room for the 5 s async-util timeout (src/test/setup.ts) inside one test.
    testTimeout: 15000,
  },
});
