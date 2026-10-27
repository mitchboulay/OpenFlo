import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import type { DeviceSummary } from '@/api/types';
import { HOME, hoursFromNow } from '@/test/fixtures';
import { renderWithApp } from '@/test/renderWithApp';
import { HomePage } from './HomePage';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const DEVICE: DeviceSummary = {
  device_id: 'D8256700000A0001',
  name: 'Lab iFLO',
  location: 'Air handler, attic',
  status: 'active',
  battery_level: 12,
  bottle_guidance: 'refill_soon',
  last_seen: hoursFromNow(-1),
  next_expected_sync: hoursFromNow(5),
  next_dose_at: null,
  pending_count: 1,
  flagged: false,
};

function serve(devices: DeviceSummary[]) {
  let patched: unknown = null;
  server.use(
    http.get('*/api/v1/homes', () => HttpResponse.json([{ ...HOME, attention_count: 1, summary: 'attention' }])),
    http.get('*/api/v1/homes/1/devices', () => HttpResponse.json(devices)),
    http.get('*/api/v1/devices/unclaimed', () =>
      HttpResponse.json([{ device_id: 'AA00BB11CC22DD33', last_ip: '192.168.30.81', first_seen: hoursFromNow(-2), last_seen: hoursFromNow(-1) }]),
    ),
    http.patch('*/api/v1/homes/1', async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json(HOME);
    }),
  );
  return () => patched;
}

function renderHome() {
  return renderWithApp(<HomePage />, { route: '/homes/:homeId', path: '/homes/1' });
}

describe('HomePage', () => {
  it('lists devices with status, bottle, battery and pending state', async () => {
    serve([DEVICE, { ...DEVICE, device_id: 'RETIRED', name: 'Old unit', status: 'retired' }]);
    renderHome();
    const card = await screen.findByRole('link', { name: /Lab iFLO/ });
    expect(card).toHaveAttribute('href', '/devices/D8256700000A0001');
    expect(within(card).getByText('Needs attention')).toBeInTheDocument();
    expect(within(card).getByText('Refill soon')).toBeInTheDocument();
    expect(within(card).getByText('12% · low')).toBeInTheDocument();
    expect(within(card).getByText(/Waiting for device · ~/)).toBeInTheDocument();
    expect(screen.queryByText('Old unit')).toBeNull();
    expect(screen.getByText('1 needs attention · 1 device')).toBeInTheDocument();
  });

  it('claims an unclaimed device into the home, saying dispensing starts off', async () => {
    serve([]);
    let claimed: unknown = null;
    server.use(
      http.post('*/api/v1/devices/AA00BB11CC22DD33/claim', async ({ request }) => {
        claimed = await request.json();
        return HttpResponse.json({ device_id: 'AA00BB11CC22DD33' });
      }),
    );
    renderHome();
    const card = await screen.findByRole('article');
    expect(within(card).getByRole('heading', { name: 'New iFLO found' })).toBeInTheDocument();
    expect(within(card).getByText('AA00BB11CC22DD33')).toBeInTheDocument();
    expect(screen.getByText('No devices in this home yet.')).toBeInTheDocument();

    await userEvent.click(within(card).getByRole('button', { name: 'Add to home…' }));
    const sheet = screen.getByRole('dialog', { name: 'Add to this home' });
    expect(within(sheet).getByText(/Dispensing starts off/)).toBeInTheDocument();
    const add = within(sheet).getByRole('button', { name: 'Add to Lab' });
    expect(add).toBeDisabled();
    await userEvent.type(within(sheet).getByLabelText('Name'), 'Garage unit');
    await userEvent.click(add);
    expect(await screen.findByText('Left the page')).toBeInTheDocument();
    expect(claimed).toEqual({ home_id: 1, name: 'Garage unit', location: null });
  });

  it('shows why a claim failed', async () => {
    serve([]);
    server.use(
      http.post('*/api/v1/devices/AA00BB11CC22DD33/claim', () =>
        HttpResponse.json({ code: 'NOT_UNCLAIMED', message: 'already claimed' }, { status: 409 }),
      ),
    );
    renderHome();
    await userEvent.click(await screen.findByRole('button', { name: 'Add to home…' }));
    const sheet = screen.getByRole('dialog', { name: 'Add to this home' });
    await userEvent.type(within(sheet).getByLabelText('Name'), 'Garage unit');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add to Lab' }));
    expect(await within(sheet).findByRole('alert')).toHaveTextContent('Someone already added this device.');
  });

  it('links to the add-device wizard', async () => {
    serve([]);
    renderHome();
    expect(await screen.findByRole('link', { name: 'Add device' })).toHaveAttribute('href', '/homes/1/add');
  });

  it('edits the home name and time zone in a sheet', async () => {
    const patched = serve([DEVICE]);
    renderHome();
    await userEvent.click(await screen.findByRole('button', { name: 'Edit home' }));
    const sheet = screen.getByRole('dialog', { name: 'Edit home' });
    const name = within(sheet).getByRole('textbox', { name: 'Name' });
    await userEvent.clear(name);
    await userEvent.type(name, 'Lab bench');
    await userEvent.selectOptions(within(sheet).getByRole('combobox', { name: 'Time zone' }), 'America/Chicago');
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save' }));
    await screen.findByRole('button', { name: 'Edit home' });
    expect(patched()).toEqual({ name: 'Lab bench', timezone: 'America/Chicago' });
  });
});
