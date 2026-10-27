import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import type { DeviceDetail, Schedule, ScheduleEntry, ScheduleRule } from '@/api/types';
import { UNITS_STORAGE_KEY } from '@/hooks/useUnits';
import { DEVICE_ID, hoursFromNow, makeDevice } from '@/test/fixtures';
import { renderWithApp } from '@/test/renderWithApp';
import { ScheduleEditor } from './ScheduleEditor';

const TZ = 'America/New_York';
const BASE = '*/api/v1';
const SUNDAY_RULE: ScheduleRule = {
  id: 7, kind: 'weekly', local_time: '09:00', days_mask: 64, interval_hours: null, at: null, dose_count: 1, enabled: true,
  summary: 'Every Sun at 09:00',
};

const server = setupServer();
let writes: { method: string; path: string; body: unknown }[] = [];
let schedule: Schedule;

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => {
  window.localStorage.setItem(UNITS_STORAGE_KEY, 'ml');
  writes = [];
  schedule = { rules: [], upcoming: [] };
  server.use(
    http.get(`${BASE}/devices/${DEVICE_ID}/schedule`, () => HttpResponse.json(schedule)),
    http.get(`${BASE}/devices/${DEVICE_ID}`, () => HttpResponse.json(makeDevice())),
    http.get(`${BASE}/homes`, () => HttpResponse.json([])),
    http.all(`${BASE}/*`, async ({ request }) => {
      const text = await request.text();
      writes.push({ method: request.method, path: new URL(request.url).pathname, body: text ? (JSON.parse(text) as unknown) : null });
      return request.method === 'DELETE' ? new HttpResponse(null, { status: 204 }) : HttpResponse.json(SUNDAY_RULE);
    }),
  );
});
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});
afterAll(() => server.close());

const on = (overrides: Partial<DeviceDetail> = {}) =>
  makeDevice({ controls: { ...makeDevice().controls, schedules_enabled: true }, ...overrides });
const entry = (id: number, at: string, status: ScheduleEntry['status'], reason: ScheduleEntry['reason'] = null): ScheduleEntry =>
  ({ id, at, dose_count: 1, status, reason, rule_ids: [7] });
const renderEditor = (device: DeviceDetail) => renderWithApp(<ScheduleEditor device={device} timeZone={TZ} />);

describe('ScheduleEditor', () => {
  it('explains once and offers one gentle rule before the device dispenses on its own', async () => {
    renderEditor(makeDevice());
    expect(screen.getByText(/Schedules are off/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('switch', { name: 'Schedules' }));
    const sheet = await screen.findByRole('dialog', { name: 'Turn on schedules' });
    expect(within(sheet).getByText('Your iFLO will dispense on its own at these times.')).toBeInTheDocument();
    expect(within(sheet).getByText('Every Sunday at 9:00 AM ET')).toBeInTheDocument();
    expect(within(sheet).getByText(/Each dose is 177 mL/)).toBeInTheDocument();
    expect(writes).toEqual([]); // nothing sent until the deliberate confirm
    await userEvent.click(within(sheet).getByRole('button', { name: 'Turn on schedules' }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes).toContainEqual({ method: 'PATCH', path: `/api/v1/devices/${DEVICE_ID}/controls`, body: { schedules_enabled: true } });
    expect(writes).toContainEqual({
      method: 'POST', path: `/api/v1/devices/${DEVICE_ID}/schedule/rules`,
      body: { kind: 'weekly', local_time: '09:00', days_mask: 64, dose_count: 1, enabled: true },
    });
  });

  it('keeps existing rules when turned back on', async () => {
    schedule = { rules: [SUNDAY_RULE], upcoming: [] };
    const view = renderEditor(makeDevice());
    await waitFor(() => expect(view.queryClient.getQueryData(['device', DEVICE_ID, 'schedule'])).toBeDefined());
    await userEvent.click(screen.getByRole('switch', { name: 'Schedules' }));
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Turn on schedules' }));
    await waitFor(() => expect(writes).toEqual([{ method: 'PATCH', path: `/api/v1/devices/${DEVICE_ID}/controls`, body: { schedules_enabled: true } }]));
  });

  it('turns off without a confirm', async () => {
    renderEditor(on());
    await userEvent.click(screen.getByRole('switch', { name: 'Schedules' }));
    await waitFor(() => expect(writes).toEqual([{ method: 'PATCH', path: `/api/v1/devices/${DEVICE_ID}/controls`, body: { schedules_enabled: false } }]));
  });

  it('adds a once rule at the home’s wall-clock time, with a plain-language preview', async () => {
    renderEditor(on());
    await userEvent.click(await screen.findByRole('button', { name: 'Add a time' }));
    const sheet = screen.getByRole('dialog', { name: 'Add a time' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Once' }));
    const date = within(sheet).getByLabelText('Date');
    await userEvent.clear(date);
    await userEvent.type(date, '2026-11-03');
    const time = within(sheet).getByLabelText('Time');
    await userEvent.clear(time);
    await userEvent.type(time, '08:00');
    await userEvent.click(within(sheet).getByRole('switch', { name: 'Double dose' }));
    expect(within(sheet).getByText('Once on Nov 3 at 8:00 AM ET · double dose')).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(writes).toEqual([{
        method: 'POST', path: `/api/v1/devices/${DEVICE_ID}/schedule/rules`,
        body: { kind: 'once', at: '2026-11-03T13:00:00.000Z', dose_count: 2, enabled: true },
      }]),
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('edits a rule’s days, and blocks saving with none', async () => {
    schedule = { rules: [SUNDAY_RULE], upcoming: [] };
    renderEditor(on());
    await userEvent.click(await screen.findByRole('button', { name: 'Every Sunday at 9:00 AM ET' }));
    const sheet = screen.getByRole('dialog', { name: 'Edit time' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Sunday' }));
    expect(within(sheet).getByText('Pick at least one day.')).toBeInTheDocument();
    expect(within(sheet).getByRole('button', { name: 'Save' })).toBeDisabled();
    await userEvent.click(within(sheet).getByRole('button', { name: 'Monday' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'Wednesday' }));
    expect(within(sheet).getByText('Every Mon, Wed at 9:00 AM ET')).toBeInTheDocument();
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(writes).toEqual([{
        method: 'PATCH', path: '/api/v1/schedule/rules/7',
        body: { kind: 'weekly', local_time: '09:00', days_mask: 0b101, dose_count: 1, enabled: true },
      }]),
    );
  });

  it('deletes a rule only on the second tap', async () => {
    schedule = { rules: [SUNDAY_RULE], upcoming: [] };
    renderEditor(on());
    await userEvent.click(await screen.findByRole('button', { name: /Every Sunday/ }));
    const sheet = screen.getByRole('dialog', { name: 'Edit time' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Delete this time' }));
    expect(writes).toEqual([]);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Tap again to delete' }));
    await waitFor(() => expect(writes).toEqual([{ method: 'DELETE', path: '/api/v1/schedule/rules/7', body: null }]));
  });

  it('lists upcoming doses in the home zone across DST, with honest statuses', async () => {
    schedule = {
      rules: [SUNDAY_RULE],
      upcoming: [
        entry(1, '2026-10-25T13:00:00Z', 'fired'), // 9:00 AM EDT
        entry(2, '2026-10-26T13:00:00Z', 'missed'),
        entry(3, '2026-10-27T13:00:00Z', 'cleared', 'too_soon'),
        entry(4, '2026-11-01T14:00:00Z', 'served'), // 9:00 AM EST, after the fall-back
        entry(5, '2026-11-08T14:00:00Z', 'pending'),
      ],
    };
    renderEditor(on({ next_expected_sync: '2026-10-26T20:42:00Z' }));
    const rows = await screen.findAllByRole('listitem');
    const upcoming = rows.filter((row) => row.textContent?.includes('9:00 AM') && !row.querySelector('button'));
    expect(upcoming.map((row) => row.textContent)).toEqual([
      'Sun, Oct 25 · 9:00 AMDispensed',
      'Mon, Oct 26 · 9:00 AMMissed',
      'Tue, Oct 27 · 9:00 AMSkipped: too close to a check-in',
      'Sun, Nov 1 · 9:00 AMOn device',
      'Sun, Nov 8 · 9:00 AMWaiting for device · ~4:42 PM',
    ]);
    expect(screen.getByRole('heading', { name: 'Upcoming · ET' })).toBeInTheDocument();
    expect(screen.queryByText(/\d{10}|T\d\d:\d\d/)).toBeNull(); // never a raw timestamp
  });

  it.each([
    ['dispensing is off', { controls: { ...on().controls, dispensing_enabled: false } }, 'Schedules are paused while dispensing is off.'],
    ['the device is flagged', {
      flags: [{
        id: 1, kind: 'ip_conflict' as const, detail: { source_ips: ['203.0.113.7'], changes: [], field: null, old: null, new: null },
        raised_at: hoursFromNow(-1), acked_at: null, acked_by: null,
      }],
    }, 'Schedules are on hold until you review the warning above.'],
    ['the device is retiring', { retire_requested_at: hoursFromNow(-1) }, 'Schedules have stopped while this device is being retired.'],
  ])('shows the paused banner, not the upcoming list, when %s', async (_, overrides, banner) => {
    schedule = { rules: [SUNDAY_RULE], upcoming: [entry(4, '2026-11-01T14:00:00Z', 'pending')] };
    renderEditor(on(overrides));
    expect(screen.getByText(banner)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /Every Sunday/ })).toBeInTheDocument();
    expect(screen.queryByText(/Upcoming/)).toBeNull();
  });
});
