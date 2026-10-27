import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ADMIN, createFakeAuthBackend, type FakeAuthOptions } from '@/test/fakeAuthBackend';
import { renderApp } from '@/test/renderWithApp';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});
afterAll(() => server.close());

function start(path = '/sign-in', options: FakeAuthOptions = {}, user = userEvent.setup()) {
  const backend = createFakeAuthBackend(options);
  server.use(...backend.handlers);
  return { backend, user, ...renderApp(path) };
}

async function signIn(user: ReturnType<typeof userEvent.setup>, password: string) {
  const field = await screen.findByLabelText('Password');
  if (!(screen.getByLabelText('Username') as HTMLInputElement).value) await user.type(screen.getByLabelText('Username'), ADMIN.username);
  await user.type(field, password);
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('Sign-in (basic)', () => {
  it('on a wrong password keeps the username, clears and focuses the password; then signs in', async () => {
    const { user, location } = start();
    await signIn(user, 'not the password');
    expect(await screen.findByRole('alert')).toHaveTextContent('That username and password don’t match.');
    expect(screen.getByLabelText('Username')).toHaveValue(ADMIN.username);
    expect(screen.getByLabelText('Password')).toHaveValue('');
    expect(screen.getByLabelText('Password')).toHaveFocus();
    expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password');

    await signIn(user, ADMIN.password);
    expect(await screen.findByRole('heading', { name: 'OpenFLO' })).toBeVisible();
    expect(location()).toBe('/');
  });

  it('on 429 disables the button with a countdown, then lets you try again', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    start('/sign-in', { rateLimited: true }, user);
    await signIn(user, ADMIN.password);
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Try again in a minute.');
    const button = screen.getByRole('button', { name: 'Try again in 42 s' });
    expect(button).toBeDisabled();
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByRole('button', { name: 'Try again in 40 s' })).toBeDisabled();
    act(() => vi.advanceTimersByTime(40_000));
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();
  });

  it('says when OpenFLO cannot be reached', async () => {
    const { user } = start();
    server.use(http.post('*/api/v1/auth/login', () => HttpResponse.error()));
    await signIn(user, ADMIN.password);
    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t reach OpenFLO. Check your connection.');
  });

  it('shows the version in the footer', async () => {
    start();
    expect(await screen.findByText('OpenFLO 0.4.0')).toBeInTheDocument();
  });
});

describe('Sign-in (other modes)', () => {
  it('oidc: one button to the identity provider, carrying next', async () => {
    start('/sign-in?next=%2Fsettings', { mode: 'oidc' });
    expect(await screen.findByRole('link', { name: 'Sign in with auth.example.com' })).toHaveAttribute(
      'href',
      '/api/v1/auth/oidc/login?next=%2Fsettings',
    );
    expect(screen.queryByLabelText('Password')).toBeNull();
  });

  it('oidc: an error on return asks to try again', async () => {
    start('/sign-in?error=OIDC_INVALID', { mode: 'oidc' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign-in didn’t finish. Try again.');
  });

  it('oidc: a group denial says who to ask', async () => {
    start('/sign-in?error=OIDC_GROUP_DENIED', { mode: 'oidc' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Your account isn’t allowed to use OpenFLO. Ask the person who runs it.');
  });

  it('proxy: a 401 asks to reload', async () => {
    start('/', { mode: 'proxy' });
    expect(await screen.findByRole('heading', { name: 'Your proxy didn’t sign you in' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
  });

  it('none: there is nothing to sign in to', async () => {
    const { location } = start('/sign-in?next=%2Fsettings', { mode: 'none' });
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeVisible();
    expect(location()).toBe('/settings');
  });
});
