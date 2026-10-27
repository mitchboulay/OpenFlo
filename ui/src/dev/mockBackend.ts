import { setupWorker } from 'msw/browser';
import { createFakeProvisioningBackend } from './fakeProvisioningBackend';

declare global {
  interface Window {
    /** Dev only (`VITE_MSW=1`): stands in for the device, e.g. `__openfloFake.advance()`. */
    __openfloFake?: ReturnType<typeof createFakeProvisioningBackend>;
  }
}

/**
 * Dev only: serves the fake `/api/v1` from a service worker so the wizard runs in a real browser.
 * `?mock=lan`, `?mock=lan-fails` and `?mock=unverified` pick the scenario.
 */
export async function startMockBackend(): Promise<void> {
  const scenario = new URLSearchParams(window.location.search).get('mock');
  const backend = createFakeProvisioningBackend({
    resetMode: scenario?.startsWith('lan') ? 'lan' : 'manual',
    lanResetFails: scenario === 'lan-fails',
    addressVerified: scenario !== 'unverified',
  });
  await setupWorker(...backend.handlers).start({ onUnhandledFrame: 'bypass', quiet: true });
  window.__openfloFake = backend;
}
