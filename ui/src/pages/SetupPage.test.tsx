import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ADMIN, createFakeAuthBackend, type FakeAuthOptions } from '@/test/fakeAuthBackend';
import { renderApp } from '@/test/renderWithApp';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

function start(options: FakeAuthOptions = {}) {
  const backend = createFakeAuthBackend({ setupRequired: true, adminExists: false, ...options });
  server.use(...backend.handlers);
  return { backend, user: userEvent.setup(), ...renderApp('/setup') };
}

type User = ReturnType<typeof userEvent.setup>;

async function toAddressStep(user: User) {
  await user.click(await screen.findByRole('button', { name: 'Continue' }));
  return screen.findByRole('heading', { name: 'Where devices find OpenFLO' });
}

async function toCheckResults(user: User, title: string) {
  await toAddressStep(user);
  await user.click(screen.getByRole('button', { name: 'Check address' }));
  return screen.findByRole('heading', { name: title });
}

const rows = () => within(screen.getByRole('list', { name: 'Address check' })).getAllByRole('listitem');

describe('Setup wizard (basic)', () => {
  it('walks account → address → failing check → done, then opens Add home', async () => {
    const { backend, user, location } = start({ checks: { tls_no_sni: 'fail' }, holdCheck: true });
    expect(await screen.findByRole('heading', { name: 'Your account' })).toBeVisible();
    expect(screen.getByText('Set up OpenFLO')).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
    const password = await screen.findByLabelText('Password');
    expect(screen.getByLabelText('Username')).toHaveAttribute('autocomplete', 'username');
    expect(password).toHaveAttribute('autocomplete', 'new-password');

    await user.type(screen.getByLabelText('Username'), ADMIN.username);
    await user.type(password, ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByRole('heading', { name: 'Where devices find OpenFLO' })).toBeVisible();
    const address = screen.getByLabelText('Server address');
    expect(address).toHaveValue('https://openflo.example.com');
    expect(address).toHaveAttribute('inputmode', 'url');
    await user.click(screen.getByRole('button', { name: 'Check address' }));

    expect(await screen.findByRole('heading', { name: 'Checking your address' })).toBeVisible();
    expect(screen.getAllByText('Checking…')).toHaveLength(5);
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
    backend.releaseCheck();

    expect(await screen.findByRole('heading', { name: 'Devices can’t reach OpenFLO yet' })).toBeVisible();
    expect(screen.getByText('You can finish setup, but adding a device stays off until this passes.')).toBeInTheDocument();
    expect(rows()[1]).toHaveTextContent('Devices can connect securelyProblem');
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByRole('heading', { name: 'OpenFLO is ready' })).toBeVisible();
    expect(await screen.findByText(/Adding a device unlocks once the address check passes/)).toBeInTheDocument();
    expect(screen.queryByText(/Step \d of 3/)).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Add a home' }));

    // Creating the admin signed us in: straight to Homes with Add home open, no sign-in on the way.
    expect(await screen.findByRole('dialog', { name: 'Add home' })).toBeVisible();
    expect(location()).toBe('/?add=home');
    expect(backend.state.requests).toEqual(['create admin', 'save https://openflo.example.com', 'check', 'complete']);
  });

  it('falls back to sign-in, then Add home, when the session is gone by the end', async () => {
    const { backend, user, location } = start();
    await user.type(await screen.findByLabelText('Username'), ADMIN.username);
    await user.type(screen.getByLabelText('Password'), ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await screen.findByRole('heading', { name: 'Where devices find OpenFLO' });
    await user.click(screen.getByRole('button', { name: 'Check address' }));
    await screen.findByRole('heading', { name: 'Everything checks out' });
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    backend.state.signedIn = false; // e.g. the cookie expired or was cleared mid-setup
    await user.click(await screen.findByRole('button', { name: 'Add a home' }));

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible();
    expect(location()).toBe('/sign-in?next=%2F%3Fadd%3Dhome');
    await user.type(screen.getByLabelText('Username'), ADMIN.username);
    await user.type(screen.getByLabelText('Password'), ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('dialog', { name: 'Add home' })).toBeVisible();
    expect(location()).toBe('/?add=home');
  });

  it('rejects a short password inline, before and from the API', async () => {
    const { backend, user } = start();
    await user.type(await screen.findByLabelText('Username'), 'admin');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Use at least 12 characters.');
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true');
    expect(backend.state.requests).toEqual([]);
  });

  it('shows a resumed account as created', async () => {
    const { user } = start({ adminExists: true });
    expect(await screen.findByText('Account created')).toBeInTheDocument();
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(await toAddressStep(user)).toBeVisible();
  });

  it('validates the address before saving', async () => {
    const { backend, user } = start({ adminExists: true, address: null });
    await toAddressStep(user);
    const field = screen.getByLabelText('Server address');
    await user.type(field, 'http://openflo.example.com');
    await user.click(screen.getByRole('button', { name: 'Check address' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Devices only connect over https://.');
    await user.clear(field);
    await user.type(field, 'openflo.example.com');
    await user.click(screen.getByRole('button', { name: 'Check address' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter the full address, starting with https://');
    expect(backend.state.requests).toEqual([]);
  });
});

describe('Setup address check states', () => {
  it('all ok: "Everything checks out"', async () => {
    const { user } = start({ adminExists: true });
    expect(await toCheckResults(user, 'Everything checks out')).toBeVisible();
    expect(rows()).toHaveLength(5);
    expect(screen.queryByText('Details')).toBeNull();
  });

  it('warnings only: "Almost there", with Cloudflare shown once', async () => {
    const { user } = start({ adminExists: true, checks: { dns: 'warn', healthcheck_reachable: 'warn' } });
    expect(await toCheckResults(user, 'Almost there')).toBeVisible();
    expect(screen.getByText('You can continue. Devices may have trouble until the warnings are fixed.')).toBeInTheDocument();
    expect(screen.getAllByText(/goes through Cloudflare/)).toHaveLength(1);
    expect(rows()[4]).toHaveTextContent('This server answeredNot checked');
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  });

  it('request failed: one notice, dim rows, Check again', async () => {
    const { backend, user } = start({ adminExists: true, checks: 'error' });
    await toAddressStep(user);
    await user.click(screen.getByRole('button', { name: 'Check address' }));
    expect(await screen.findByText('Couldn’t run the check. Check again.')).toBeInTheDocument();
    expect(screen.getAllByText('Not checked')).toHaveLength(5);
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Check again' }));
    await waitFor(() => expect(backend.state.requests.filter((request) => request === 'check')).toHaveLength(2));
  });

  it('Change goes back to the address step', async () => {
    const { user } = start({ adminExists: true });
    await toCheckResults(user, 'Everything checks out');
    await user.click(screen.getByRole('button', { name: 'Change' }));
    expect(await screen.findByRole('heading', { name: 'Where devices find OpenFLO' })).toBeVisible();
  });
});

describe('Setup in other auth modes', () => {
  it('oidc reachable: the issuer is connected', async () => {
    start({ mode: 'oidc' });
    expect(await screen.findByText('Sign-in is handled by auth.example.com.')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled();
  });

  it('oidc unreachable: the fix, and Continue stays off', async () => {
    start({ mode: 'oidc', oidcReachable: false });
    expect(await screen.findByText('Can’t reach it')).toBeInTheDocument();
    expect(screen.getByText('Check OPENFLO_OIDC_ISSUER and that the server can reach it.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  });

  it('proxy: nothing to set up', async () => {
    const { user } = start({ mode: 'proxy' });
    expect(await screen.findByText('Sign-in is handled by your reverse proxy.')).toBeInTheDocument();
    expect(await toAddressStep(user)).toBeVisible();
  });

  it('none: warns, links the docs, and continues', async () => {
    const { user } = start({ mode: 'none' });
    expect(await screen.findByText(/Anyone who can reach this page can use it/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'How to turn on sign-in' })).toHaveAttribute('href', expect.stringContaining('deploy.md#sign-in'));
    expect(await toAddressStep(user)).toBeVisible();
  });
});

describe('Setup secrets', () => {
  it('keeps the new password out of storage, the caches, the console and the page', async () => {
    const spies = (['log', 'info', 'warn', 'error'] as const).map((method) => vi.spyOn(console, method));
    const { user, queryClient } = start();
    await user.type(await screen.findByLabelText('Username'), ADMIN.username);
    await user.type(screen.getByLabelText('Password'), ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await screen.findByRole('heading', { name: 'Where devices find OpenFLO' });
    const traces = [
      JSON.stringify({ ...localStorage }),
      JSON.stringify({ ...sessionStorage }),
      JSON.stringify(queryClient.getQueryCache().getAll().map((query) => query.state.data)),
      JSON.stringify(queryClient.getMutationCache().getAll().map((mutation) => [mutation.state.variables, mutation.state.data])),
      document.body.innerHTML,
      ...spies.flatMap((spy) => spy.mock.calls.map((call) => call.map(String).join(' '))),
    ];
    expect(traces.filter((text) => text.includes(ADMIN.password))).toEqual([]);
  });
});
