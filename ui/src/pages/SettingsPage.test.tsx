import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { UNITS_STORAGE_KEY } from '@/hooks/useUnits';
import { createFakeAuthBackend, FAKE_API_TOKEN, type FakeAuthOptions } from '@/test/fakeAuthBackend';
import { makeCheckResult, makeToken } from '@/test/fixtures';
import { renderApp } from '@/test/renderWithApp';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
  sessionStorage.clear();
});
afterAll(() => server.close());

function start(options: FakeAuthOptions = {}) {
  const backend = createFakeAuthBackend({ signedIn: true, ...options });
  server.use(...backend.handlers);
  return { backend, user: userEvent.setup(), ...renderApp('/settings') };
}

const card = (name: string) => screen.findByRole('region', { name });

describe('Settings → Server address', () => {
  it('folds a passing check behind its summary line', async () => {
    const { user } = start({ lastCheck: makeCheckResult() });
    const section = await card('Server address');
    expect(within(section).getByText('https://openflo.example.com')).toBeInTheDocument();
    const summary = await within(section).findByRole('button', { name: /Checked 5 minutes ago · Everything checks out/ });
    expect(summary).toHaveAttribute('aria-expanded', 'false');
    expect(within(section).queryByRole('list', { name: 'Address check' })).toBeNull();
    await user.click(summary);
    const list = within(section).getByRole('list', { name: 'Address check' });
    expect(list).toBeVisible();
    // Each OK row uses the ok tone, as in setup; never the neutral grey of "Checking…".
    const statuses = within(list).getAllByText('OK');
    expect(statuses.length).toBeGreaterThan(0);
    for (const status of statuses) {
      expect(status).toHaveClass('text-ok');
      expect(status.querySelector('[aria-hidden]')).toHaveClass('bg-ok');
    }
  });

  it('opens a check with problems', async () => {
    start({ lastCheck: makeCheckResult({ port_non_443: 'warn' }) });
    const section = await card('Server address');
    expect(await within(section).findByText(/· 1 warning/)).toBeInTheDocument();
    expect(within(section).getByRole('list', { name: 'Address check' })).toBeVisible();
  });

  it('Change saves the new address and re-runs the check', async () => {
    const { backend, user } = start({ lastCheck: makeCheckResult(), checks: { leaf_rsa: 'fail' } });
    const section = await card('Server address');
    await user.click(within(section).getByRole('button', { name: 'Change' }));
    const dialog = await screen.findByRole('dialog', { name: 'Server address' });
    const field = within(dialog).getByLabelText('Server address');
    await user.clear(field);
    await user.type(field, 'https://flo.example.net');
    await user.click(within(dialog).getByRole('button', { name: 'Save and check' }));

    expect(await within(section).findByText('https://flo.example.net')).toBeInTheDocument();
    expect(await within(section).findByText(/Devices can’t connect/)).toBeInTheDocument();
    expect(backend.state.requests).toEqual(['save https://flo.example.net', 'check']);
  });
});

describe('Settings → Units', () => {
  it('persists the choice', async () => {
    const { user } = start();
    const section = await card('Units');
    await user.click(within(section).getByRole('button', { name: 'Ounces (oz)' }));
    expect(within(section).getByRole('button', { name: 'Ounces (oz)' })).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem(UNITS_STORAGE_KEY)).toBe('oz');
  });
});

describe('Settings → Sign-in', () => {
  it('shows the method and the actor, and signs out', async () => {
    const { backend, user, location } = start();
    const section = await card('Sign-in');
    expect(within(section).getByText('Username and password')).toBeInTheDocument();
    expect(await within(section).findByText('admin')).toBeInTheDocument();
    await user.click(within(section).getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible();
    expect(location()).toBe('/sign-in');
    expect(backend.state.requests).toEqual(['logout']);
  });

  it('says sign-in is off in mode none, without Sign out', async () => {
    start({ mode: 'none' });
    const section = await card('Sign-in');
    expect(within(section).getByText('Off')).toBeInTheDocument();
    expect(await within(section).findByText('Local operator')).toBeInTheDocument();
    expect(within(section).getByText(/Sign-in is off/)).toBeInTheDocument();
    expect(within(section).queryByRole('button', { name: 'Sign out' })).toBeNull();
  });
});

describe('Settings → API tokens', () => {
  it('lists tokens; revoke is two-step; the bootstrap token cannot be revoked here', async () => {
    const tokens = [
      makeToken({ id: 1, name: 'Home Assistant', last_used_at: new Date(Date.now() - 3 * 3_600_000).toISOString() }),
      makeToken({ id: 2, name: 'Server config', kind: 'bootstrap', fingerprint: 'deadbeef' }),
    ];
    const { backend, user } = start({ tokens });
    const section = await card('API tokens');
    const list = await within(section).findByRole('list', { name: 'API tokens' });
    const [personal, bootstrap] = within(list).getAllByRole('listitem');
    expect(personal).toHaveTextContent('Last used 3 hours ago · …a1b2c3d4');
    expect(bootstrap).toHaveTextContent('Last used never · …deadbeef');
    expect(bootstrap).toHaveTextContent('From server config');
    expect(bootstrap).toHaveTextContent('Remove OPENFLO_API_TOKEN to revoke');
    expect(within(bootstrap as HTMLElement).queryByRole('button')).toBeNull();

    await user.click(within(personal as HTMLElement).getByRole('button', { name: 'Revoke' }));
    expect(backend.state.requests).toEqual([]);
    await user.click(within(personal as HTMLElement).getByRole('button', { name: 'Revoke Home Assistant?' }));
    await waitFor(() => expect(within(section).queryByText('Home Assistant')).toBeNull());
    expect(backend.state.requests).toEqual(['revoke 1']);
  });

  it('shows "No tokens yet." when there are none', async () => {
    start();
    expect(await within(await card('API tokens')).findByText('No tokens yet.')).toBeInTheDocument();
  });

  it('shows a new token once, then keeps it out of storage, caches, logs, the URL and the page', async () => {
    const spies = (['log', 'info', 'warn', 'error'] as const).map((method) => vi.spyOn(console, method));
    const { user, queryClient } = start();
    const section = await card('API tokens');
    await user.click(within(section).getByRole('button', { name: 'New token…' }));
    const dialog = await screen.findByRole('dialog', { name: 'New token' });
    await user.type(within(dialog).getByLabelText('Name'), 'Grafana');
    await user.click(within(dialog).getByRole('button', { name: 'Create' }));

    const created = await screen.findByRole('dialog', { name: 'Copy your token' });
    expect(within(created).getByLabelText('New token')).toHaveTextContent(FAKE_API_TOKEN);
    expect(within(created).getByText('You won’t see this again. Store it somewhere safe.')).toBeInTheDocument();
    await user.click(within(created).getByRole('button', { name: 'Copy' }));
    expect(await navigator.clipboard.readText()).toBe(FAKE_API_TOKEN);
    expect(within(created).getByRole('button', { name: 'Copied' })).toBeInTheDocument();
    expect(await within(section).findByText('Grafana')).toBeInTheDocument();

    const leaks = () =>
      [
        JSON.stringify({ ...localStorage }),
        JSON.stringify({ ...sessionStorage }),
        JSON.stringify(queryClient.getQueryCache().getAll().map((query) => query.state.data)),
        JSON.stringify(queryClient.getMutationCache().getAll().map((mutation) => [mutation.state.variables, mutation.state.data])),
        document.cookie,
        window.location.href,
        ...spies.flatMap((spy) => spy.mock.calls.map((call) => call.map(String).join(' '))),
      ].filter((text) => text.includes(FAKE_API_TOKEN));
    expect(leaks()).toEqual([]);

    await user.click(within(created).getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.body.innerHTML).not.toContain(FAKE_API_TOKEN);
    expect(leaks()).toEqual([]);

    // Reopening starts fresh: the token is gone for good.
    await user.click(within(section).getByRole('button', { name: 'New token…' }));
    expect(await screen.findByRole('dialog', { name: 'New token' })).toBeVisible();
    expect(document.body.innerHTML).not.toContain(FAKE_API_TOKEN);
  });
});

describe('Settings → About', () => {
  it('shows the version', async () => {
    start();
    expect(within(await card('About')).getByText('0.4.0')).toBeInTheDocument();
  });
});
