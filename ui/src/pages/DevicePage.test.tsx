import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import type { DeviceDetail } from '@/api/types';
import { DEVICE_ID, HOME, hoursFromNow, makeDevice } from '@/test/fixtures';
import { renderWithApp } from '@/test/renderWithApp';
import { DevicePage } from './DevicePage';

const DEVICE_URL = `*/api/v1/devices/${DEVICE_ID}`;

interface Seen {
  method: string;
  path: string;
  body: unknown;
}

const server = setupServer();
let seen: Seen[] = [];
let current: DeviceDetail;

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function record(request: Request): Promise<void> {
  const text = await request.text();
  seen.push({ method: request.method, path: new URL(request.url).pathname, body: text ? (JSON.parse(text) as unknown) : null });
}

/** Serves `device` and records writes; `onWrite` may change what the next GET returns. */
function serve(device: DeviceDetail, onWrite: (path: string, body: unknown) => Response | undefined = () => undefined) {
  seen = [];
  current = device;
  server.use(
    http.get('*/api/v1/homes', () => HttpResponse.json([HOME])),
    http.get(DEVICE_URL, () => HttpResponse.json(current)),
    http.get(`${DEVICE_URL}/battery`, () => HttpResponse.json({ points: [], projection_days_to_20: null, basis_days: null })),
    http.get(`${DEVICE_URL}/schedule`, () => HttpResponse.json({ rules: [], upcoming: [] })),
    http.get(`${DEVICE_URL}/history`, () => HttpResponse.json({ kind: 'dispenses', items: [], next_before_id: null })),
    http.get('*/api/v1/liquid-profiles', () => HttpResponse.json([device.dosing.profile])),
    http.all('*/api/v1/*', async ({ request }) => {
      await record(request);
      const last = seen[seen.length - 1];
      return onWrite(last?.path ?? '', last?.body) ?? HttpResponse.json(current);
    }),
  );
}

function renderDevice() {
  return renderWithApp(<DevicePage />, { route: '/devices/:deviceId', path: `/devices/${DEVICE_ID}` });
}

const header = () => screen.getByRole('region', { name: 'Status' });

describe('DevicePage', () => {
  it('shows the headline, sync honesty and the dispensing state', async () => {
    serve(makeDevice());
    renderDevice();
    expect(await screen.findByRole('heading', { name: 'Lab iFLO' })).toBeInTheDocument();
    expect(within(header()).getByText(/^Everything’s fine\. Next check-in around/)).toBeInTheDocument();
    expect(within(header()).getByText(/Last check-in .* · next around/)).toBeInTheDocument();
    expect(within(header()).getByText('Dispensing · On')).toBeInTheDocument();
    expect(within(header()).getByText(/To make it check in now, twist the bottle/)).toBeInTheDocument();
  });

  it('names each pending change as waiting for the device', async () => {
    serve(makeDevice({ pending: [{ kind: 'dose', since: hoursFromNow(-0.1) }, { kind: 'controls', since: hoursFromNow(-0.1) }] }));
    renderDevice();
    const list = await screen.findByRole('list', { name: 'Waiting for device' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringMatching(/^Dose change.*Waiting for device · ~/),
      expect.stringMatching(/^Dispensing or check-in change.*Waiting for device · ~/),
    ]);
    expect(within(header()).getByText(/To apply now, twist the bottle/)).toBeInTheDocument();
  });

  it('pauses dispensing from the menu and keeps showing the server state until it changes', async () => {
    serve(makeDevice());
    renderDevice();
    await userEvent.click(await screen.findByRole('button', { name: 'Device actions' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Pause dispensing' }));
    await waitFor(() => expect(seen).toContainEqual({ method: 'PATCH', path: `/api/v1/devices/${DEVICE_ID}/controls`, body: { dispensing_enabled: false } }));
    // The mock server did not change: no optimistic "Paused".
    expect(within(header()).getByText('Dispensing · On')).toBeInTheDocument();
  });

  it('says dispensing is paused and offers Resume', async () => {
    serve(makeDevice({ controls: { ...makeDevice().controls, dispensing_enabled: false } }));
    renderDevice();
    expect(await within(await screen.findByRole('region', { name: 'Status' })).findByText('Dispensing is paused.')).toBeInTheDocument();
    expect(within(header()).getByText('Dispensing · Paused')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Device actions' }));
    expect(screen.getByRole('menuitem', { name: 'Resume dispensing' })).toBeInTheDocument();
  });

  it('dispenses only after the second step, then tracks the queued request', async () => {
    serve(makeDevice(), (path) => {
      if (path.endsWith('/dispense')) {
        const request = { id: 7, requested_at: hoursFromNow(0), delivered_at: null, cancelled_at: null, confirmed_at: null };
        current = { ...current, pending: [{ kind: 'dispense', since: request.requested_at }], remote_dispense: { pending: request, last_delivered: null } };
        return HttpResponse.json(request);
      }
      return undefined;
    });
    renderDevice();
    await userEvent.click(await screen.findByRole('button', { name: 'Dispense now…' }));
    expect(seen).toEqual([]);
    expect(screen.getByText(/Dispense .* of cartridge liquid\?/)).toBeInTheDocument();
    expect(screen.getByText(/it will dispense once when it next checks in, around/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Yes, dispense' }));
    expect(await screen.findByText('Queued for next check-in')).toBeInTheDocument();
    expect(seen).toEqual([{ method: 'POST', path: `/api/v1/devices/${DEVICE_ID}/dispense`, body: null }]);
    expect(screen.getByRole('button', { name: 'Cancel request' })).toBeInTheDocument();
  });

  it('can back out of the dispense confirm without sending anything', async () => {
    serve(makeDevice());
    renderDevice();
    await userEvent.click(await screen.findByRole('button', { name: 'Dispense now…' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeInTheDocument();
    expect(seen).toEqual([]);
  });

  it('holds commands behind an identity flag until acknowledged', async () => {
    const flag = {
      id: 3,
      kind: 'ip_conflict' as const,
      detail: { source_ips: ['203.0.113.7', '192.168.30.80'], changes: [], field: null, old: null, new: null },
      raised_at: hoursFromNow(-1),
      acked_at: null,
      acked_by: null,
    };
    serve(makeDevice({ flags: [flag] }), (path) => {
      if (path === '/api/v1/flags/3/ack') {
        current = { ...current, flags: [{ ...flag, acked_at: hoursFromNow(0), acked_by: 'operator:local' }] };
        return HttpResponse.json(current.flags[0]);
      }
      return undefined;
    });
    renderDevice();
    const warning = await screen.findByRole('region', { name: 'Device warning' });
    expect(within(warning).getByText('Checked in from 203.0.113.7')).toBeInTheDocument();
    expect(within(header()).getByText(/on hold until you review the warning/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeDisabled();
    await userEvent.click(within(warning).getByRole('button', { name: 'It’s fine (I moved it)' }));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Device warning' })).toBeNull());
    expect(screen.getByRole('button', { name: 'Dispense now…' })).toBeEnabled();
  });

  it('retires in two phases: pending until the schedule clears, then Retire anyway', async () => {
    serve(makeDevice(), (path, body) => {
      if (!path.endsWith('/retire')) return undefined;
      const force = (body as { force: boolean }).force;
      current = force
        ? { ...current, status: 'retired' }
        : { ...current, retire_requested_at: hoursFromNow(0), pending: [{ kind: 'retire', since: hoursFromNow(0) }] };
      return HttpResponse.json(current, { status: force ? 200 : 202 });
    });
    renderDevice();
    await userEvent.click(await screen.findByRole('button', { name: 'Device actions' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Retire device…' }));
    const sheet = screen.getByRole('dialog', { name: 'Retire Lab iFLO' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Retire device' }));
    expect(seen).toEqual([]);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Tap again to retire' }));
    expect(await within(sheet).findByText(/Waiting for the device to clear its schedule/)).toBeInTheDocument();
    expect(seen[0]).toEqual({ method: 'POST', path: `/api/v1/devices/${DEVICE_ID}/retire`, body: { force: false } });
    expect(within(header()).getByText('Retiring')).toBeInTheDocument();
    expect(within(sheet).getByText(/may keep dispensing on its own schedule until its bottle is removed/)).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole('button', { name: 'Retire anyway' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'Tap again to retire anyway' }));
    expect(await screen.findByText('Left the page')).toBeInTheDocument();
    expect(seen[1]?.body).toEqual({ force: true });
  });

  it('selects a check-in preset; Testing only under Advanced', async () => {
    serve(makeDevice());
    renderDevice();
    const group = await screen.findByRole('radiogroup', { name: 'Check-in' });
    expect(within(group).getAllByRole('radio').map((radio) => radio.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    expect(within(group).queryByRole('radio', { name: /Testing/ })).toBeNull();
    await userEvent.click(within(group).getByRole('radio', { name: /Responsive/ }));
    await waitFor(() => expect(seen).toContainEqual({ method: 'PATCH', path: `/api/v1/devices/${DEVICE_ID}/controls`, body: { wake_preset: 'responsive' } }));
    const checkin = screen.getByRole('region', { name: 'Check-in' });
    await userEvent.click(within(checkin).getByRole('button', { name: 'Advanced' }));
    expect(within(group).getByRole('radio', { name: /Testing/ })).toHaveTextContent('Drains the battery');
  });

  it('describes an offline device by when it was last heard from', async () => {
    serve(makeDevice({ last_seen: hoursFromNow(-30), last_sync: hoursFromNow(-30), next_expected_sync: hoursFromNow(-24) }));
    renderDevice();
    expect(await screen.findByText(/We haven’t heard from it since/)).toBeInTheDocument();
    expect(within(header()).getByText('Offline')).toBeInTheDocument();
    expect(within(header()).getByText(/missed since/)).toBeInTheDocument();
  });
});
