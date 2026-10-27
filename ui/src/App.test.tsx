import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { ADMIN, createFakeAuthBackend, type FakeAuthOptions } from '@/test/fakeAuthBackend';
import { renderApp } from '@/test/renderWithApp';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function start(path: string, options: FakeAuthOptions = { signedIn: true }) {
  const backend = createFakeAuthBackend(options);
  server.use(...backend.handlers);
  return { backend, user: userEvent.setup(), ...renderApp(path) };
}

describe('App boot routing', () => {
  it('renders Homes at / once signed in, with the Settings gear', async () => {
    start('/');
    expect(await screen.findByRole('heading', { name: 'OpenFLO' })).toBeVisible();
    expect(screen.getByRole('link', { name: /Lab/ })).toHaveAttribute('href', '/homes/1');
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings');
  });

  it('redirects unknown routes to Homes', async () => {
    const { location } = start('/nowhere');
    expect(await screen.findByRole('heading', { name: 'OpenFLO' })).toBeVisible();
    expect(location()).toBe('/');
  });

  it('sends every URL to setup while setup is required', async () => {
    const { location } = start('/devices/D8256700000A0001', { setupRequired: true, adminExists: false });
    expect(await screen.findByRole('heading', { name: 'Your account' })).toBeVisible();
    expect(location()).toBe('/setup');
  });

  it('leaves /setup for Homes with Add home open once setup is done', async () => {
    const { location } = start('/setup');
    expect(await screen.findByRole('dialog', { name: 'Add home' })).toBeVisible();
    expect(location()).toBe('/?add=home');
  });

  it('sends a 401 to sign-in with ?next=, and back there after signing in', async () => {
    const { user, location } = start('/settings?tab=x', { signedIn: false });
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible();
    expect(location()).toBe('/sign-in?next=%2Fsettings%3Ftab%3Dx');
    await user.type(screen.getByLabelText('Username'), ADMIN.username);
    await user.type(screen.getByLabelText('Password'), ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeVisible();
    await waitFor(() => expect(location()).toBe('/settings?tab=x'));
  });

  it('never follows ?next= off this app', async () => {
    const { user, location } = start('/sign-in?next=//evil.example.com', { signedIn: false });
    await user.type(await screen.findByLabelText('Username'), ADMIN.username);
    await user.type(screen.getByLabelText('Password'), ADMIN.password);
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('heading', { name: 'OpenFLO' })).toBeVisible();
    expect(location()).toBe('/');
  });

  it('serves the component gallery in dev', async () => {
    start('/__components');
    expect(await screen.findByRole('heading', { name: 'Components' }, { timeout: 5000 })).toBeVisible();
    expect(screen.getAllByRole('switch').length).toBeGreaterThan(0);
  });
});

describe('NoLoginBanner', () => {
  const BANNER = /No login.*anyone on your network can control your devices/;

  it('tops every app page in auth mode none, as a status with the docs link', async () => {
    const { user } = start('/', { mode: 'none' });
    const banner = (await screen.findByText('No login')).closest('[role="status"]');
    expect(banner).toHaveTextContent(BANNER);
    expect(screen.getByRole('link', { name: 'Turn on sign-in' })).toHaveAttribute('target', '_blank');
    await user.click(screen.getByRole('link', { name: 'Settings' }));
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeVisible();
    expect(screen.getByText('No login').closest('[role="status"]')).toHaveTextContent(BANNER);
  });

  it('is absent on setup, even in mode none', async () => {
    start('/setup', { mode: 'none', setupRequired: true });
    expect(await screen.findByRole('heading', { name: 'Your account' })).toBeVisible();
    expect(screen.queryByText(/No login/)).toBeNull();
  });

  it('is absent when sign-in is on', async () => {
    start('/');
    expect(await screen.findByRole('heading', { name: 'OpenFLO' })).toBeVisible();
    expect(screen.queryByText(/No login/)).toBeNull();
  });
});
