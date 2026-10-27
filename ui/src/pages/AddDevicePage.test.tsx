import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { createFakeProvisioningBackend, FAKE_TOKEN, NEW_DEVICE_ID, type FakeBackendOptions } from '@/dev/fakeProvisioningBackend';
import { DEVICE_ID } from '@/test/fixtures';
import { renderWithApp } from '@/test/renderWithApp';
import { AddDevicePage } from './AddDevicePage';

// The wizard polls every 2 s in production; the tests poll every 20 ms so they never race vitest's 5 s timeout.
vi.mock('@/api/queryKeys', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/queryKeys')>()),
  PROVISIONING_POLL_MS: 20,
}));

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
  sessionStorage.clear();
});
afterAll(() => server.close());

/** Many test poll intervals: the wizard follows the device by polling. */
const POLL = { timeout: 2000 };

function start(path = '/homes/1/add', options: FakeBackendOptions = {}) {
  const backend = createFakeProvisioningBackend(options);
  server.use(...backend.handlers);
  const user = userEvent.setup();
  const view = renderWithApp(<AddDevicePage />, { route: '/homes/:homeId/add/:sessionId?', path });
  return { backend, user, ...view };
}

async function submitDetails(user: ReturnType<typeof userEvent.setup>, name?: string) {
  if (name) await user.type(await screen.findByLabelText('Name'), name);
  await user.click(await screen.findByRole('button', { name: 'Continue' }));
}

describe('AddDevicePage (provisioning wizard)', () => {
  it('adds a new device: details, both QR codes, live progress, done', async () => {
    const { backend, user } = start();
    expect(await screen.findByRole('heading', { name: 'Name it' })).toBeVisible();
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Hall closet' }));
    await submitDetails(user, 'Attic unit');

    expect(await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' })).toBeVisible();
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'QR code to join Wi-Fi network iFLO device' })).toBeInTheDocument();
    expect(screen.getByText('iFLO device')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'I’ve joined it' }));

    expect(await screen.findByRole('heading', { name: 'Open the setup page' })).toBeVisible();
    expect(screen.getByRole('img', { name: 'QR code to open the iFLO setup page' })).toBeInTheDocument();
    expect(screen.getByText('http://192.168.4.1')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Copy link' }));
    expect(await navigator.clipboard.readText()).toBe(
      `http://192.168.4.1/index.html?ott=${FAKE_TOKEN}&apiUrl=https://openflo.example.com&deviceType=0`,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Link copied.');
    await user.click(screen.getByRole('button', { name: 'I’ve finished on my phone' }));

    const progress = await screen.findByRole('list', { name: 'Setup progress' });
    expect(screen.getByRole('heading', { name: 'Connecting Attic unit' })).toBeVisible();
    expect(within(progress).getByText('Found on your network').closest('li')).toHaveAttribute('aria-current', 'step');
    backend.advance();
    await waitFor(() => expect(within(progress).getByText('Registered').closest('li')).toHaveAttribute('aria-current', 'step'), POLL);
    expect(within(progress).getByText('Found on your network').closest('li')).toHaveTextContent('Done');
    backend.advance();

    expect(await screen.findByRole('heading', { name: 'Attic unit is ready.' }, POLL)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Go to Attic unit' })).toHaveAttribute('href', `/devices/${NEW_DEVICE_ID}`);
    expect(backend.requests).toEqual(['create new']);
  });

  it('keeps the one-time token out of storage, logs, the query cache and page text', async () => {
    const log = vi.spyOn(console, 'log');
    const warn = vi.spyOn(console, 'warn');
    const err = vi.spyOn(console, 'error');
    const { user, queryClient, unmount } = start();
    await submitDetails(user, 'Attic unit');
    await user.click(await screen.findByRole('button', { name: 'I’ve joined it' }));
    expect(await screen.findByRole('img', { name: 'QR code to open the iFLO setup page' })).toBeInTheDocument();

    const leaks = () => [
      JSON.stringify({ ...localStorage }),
      JSON.stringify({ ...sessionStorage }),
      JSON.stringify(queryClient.getQueryCache().getAll().map((query) => query.state.data)),
      JSON.stringify(queryClient.getMutationCache().getAll().map((mutation) => mutation.state.data)),
      document.cookie,
      window.location.href,
      ...[log, warn, err].flatMap((spy) => spy.mock.calls.map((call) => call.map(String).join(' '))),
    ].filter((text) => text.includes(FAKE_TOKEN));

    expect(document.body.innerHTML).not.toContain(FAKE_TOKEN);
    expect(leaks()).toEqual([]);
    unmount();
    expect(leaks()).toEqual([]);
  });

  it('resets a device it can reach over the LAN with "Reset now"', async () => {
    const { backend, user } = start(`/homes/1/add?device=${DEVICE_ID}`, { resetMode: 'lan' });
    expect(await screen.findByRole('heading', { name: 'Move to a new network' })).toBeVisible();
    expect(await screen.findByDisplayValue('Attic unit')).toBeInTheDocument();
    await submitDetails(user);

    expect(await screen.findByRole('heading', { name: 'Reset it' })).toBeVisible();
    expect(screen.getByText('Step 2 of 6')).toBeInTheDocument();
    expect(await screen.findByText(/It next checks in around/, {}, POLL)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reset now' }));
    expect(await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' })).toBeVisible();
    expect(screen.getByText('Step 3 of 6')).toBeInTheDocument();
    expect(backend.requests).toEqual(['create reset', 'reset']);
  });

  it('falls back to holding the reset button when the LAN reset fails', async () => {
    const { backend, user } = start(`/homes/1/add?device=${DEVICE_ID}`, { resetMode: 'lan', lanResetFails: true });
    await submitDetails(user);
    await user.click(await screen.findByRole('button', { name: 'Reset now' }));
    expect(await screen.findByText('Couldn’t reach the device. Hold its reset button instead.')).toBeInTheDocument();
    expect(screen.getByText(/Hold the reset button on the device/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'I’ve reset it' }));
    expect(await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' })).toBeVisible();
    expect(backend.requests).toEqual(['create reset', 'reset', 'manual-reset']);
  });

  it('says when a setup timed out and starts again with the same details', async () => {
    const { backend, user } = start();
    await submitDetails(user, 'Attic unit');
    await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' });
    backend.expire();
    expect(await screen.findByRole('heading', { name: 'This setup timed out.' }, POLL)).toBeVisible();
    expect(screen.queryByRole('img', { name: /QR code/ })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Start again' }));
    expect(await screen.findByRole('heading', { name: 'Name it' })).toBeVisible();
    expect(screen.getByLabelText('Name')).toHaveValue('Attic unit');
  });

  it('redirects to the home’s open setup instead of starting a second one', async () => {
    const { backend, user } = start();
    backend.openElsewhere();
    await submitDetails(user, 'Attic unit');
    expect(await screen.findByText('A setup was already in progress in this home, so you’re continuing it.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Use your phone' })).toBeVisible();
    expect(screen.getByText(/shown only once/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'I’ve finished on my phone' }));
    expect(await screen.findByRole('heading', { name: 'Connecting Basement unit' })).toBeVisible();
  });

  it('blocks provisioning on an unverified server address and links to Settings', async () => {
    const { user } = start('/homes/1/add', { addressVerified: false });
    await submitDetails(user, 'Attic unit');
    const notice = await screen.findByRole('alert');
    expect(notice).toHaveTextContent('Your devices can’t reach this server’s address yet.');
    expect(within(notice).getByRole('link', { name: 'Open Settings' })).toHaveAttribute('href', '/settings');
    expect(screen.getByRole('heading', { name: 'Name it' })).toBeVisible();
  });

  it('asks before cancelling, then cancels the session and leaves', async () => {
    const { backend, user } = start();
    await submitDetails(user, 'Attic unit');
    // Both screens have a Cancel; wait for the session's first screen so the click isn't the details one.
    await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' });
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(await screen.findByRole('heading', { name: 'Stop setting up?' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Keep going' }));
    expect(await screen.findByRole('heading', { name: 'Join the device’s Wi-Fi' })).toBeVisible();
    await user.click(await screen.findByRole('button', { name: 'Cancel' }));
    await user.click(await screen.findByRole('button', { name: 'Stop setup' }));
    expect(await screen.findByText('Left the page')).toBeInTheDocument();
    expect(backend.requests).toEqual(['create new', 'cancel']);
  });
});
