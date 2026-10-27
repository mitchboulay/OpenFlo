import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import type { DeviceDetail, Profile } from '@/api/types';
import { UNITS_STORAGE_KEY } from '@/hooks/useUnits';
import { DEVICE_ID, makeDevice, makeDosing } from '@/test/fixtures';
import { renderWithApp } from '@/test/renderWithApp';
import { DosingCard } from './DosingCard';

const STANDARD = makeDosing().profile;
const VINEGAR: Profile = { ...STANDARD, id: 2, slug: 'vinegar', name: 'Vinegar', capacity_ml: 1000, default_dose_ml: 120, calibrated: false };
const DOSING_URL = `*/api/v1/devices/${DEVICE_ID}/dosing`;

const server = setupServer();
let puts: unknown[] = [];

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }));
beforeEach(() => {
  window.localStorage.setItem(UNITS_STORAGE_KEY, 'ml');
  puts = [];
  server.use(
    http.get('*/api/v1/liquid-profiles', () => HttpResponse.json([STANDARD, VINEGAR])),
    http.get(`*/api/v1/devices/${DEVICE_ID}`, () => HttpResponse.json(makeDevice())),
    http.get('*/api/v1/homes', () => HttpResponse.json([])),
  );
});
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});
afterAll(() => server.close());

function onPut(respond: (body: unknown) => Response) {
  server.use(
    http.put(DOSING_URL, async ({ request }) => {
      const body = await request.json();
      puts.push(body);
      return respond(body);
    }),
  );
}

function renderCard(device: DeviceDetail = makeDevice()) {
  return renderWithApp(<DosingCard device={device} />);
}

describe('DosingCard', () => {
  it('shows only Liquid, Dose and Bottle, with the API values', async () => {
    renderCard();
    const card = screen.getByRole('region', { name: 'Dosing' });
    expect(within(card).getByRole('status', { name: 'Dose' })).toHaveTextContent('177mL');
    expect(within(card).getByText('≈ 6.0 oz')).toBeInTheDocument();
    expect(within(card).getByText('Measured 27.2 mL/s')).toBeInTheDocument();
    expect(within(card).queryByRole('switch')).toBeNull();
    expect(within(card).queryByText(/Dispense/)).toBeNull();
    expect(within(card).queryByText(/\d s\b/)).toBeNull(); // seconds only in Advanced
    expect(await within(card).findByRole('button', { name: /Vinegar Not calibrated yet/ })).toBeInTheDocument();
  });

  it('switches liquid to the new liquid’s usual dose', async () => {
    onPut(() => HttpResponse.json(makeDosing()));
    renderCard();
    await userEvent.click(await screen.findByRole('button', { name: /Vinegar/ }));
    await waitFor(() => expect(puts).toEqual([{ profile_id: 2, dose_ml: 120, compensation_enabled: true }]));
  });

  it('labels presets Light · Standard · Strong with volumes, and sends the picked one', async () => {
    onPut(() => HttpResponse.json(makeDosing()));
    renderCard();
    const presets = screen.getByRole('group', { name: 'Dose presets' });
    expect(within(presets).getByRole('button', { name: 'Standard 177 mL' })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(within(presets).getByRole('button', { name: 'Strong 236 mL' }));
    await waitFor(() => expect(puts).toEqual([{ profile_id: 1, dose_ml: 236, compensation_enabled: true }]));
  });

  it('bounds the stepper by the API’s limits and says what the liquid can dose', async () => {
    renderCard(makeDevice({ dosing: makeDosing({ dose_ml: 816 }) }));
    expect(screen.getByRole('button', { name: 'More dose' })).toBeDisabled();
    expect(screen.getByText('This liquid can dose 28–816 mL')).toBeInTheDocument();
    renderCard(makeDevice({ dosing: makeDosing({ dose_ml: 28 }) }));
    expect(screen.getAllByRole('button', { name: 'Less dose' })[1]).toBeDisabled();
  });

  it('steps by 5 mL and commits once the taps pause', async () => {
    onPut(() => HttpResponse.json(makeDosing()));
    renderCard();
    await userEvent.click(screen.getByRole('button', { name: 'More dose' }));
    await userEvent.click(screen.getByRole('button', { name: 'More dose' }));
    expect(screen.getByRole('status', { name: 'Dose' })).toHaveTextContent('185mL');
    await waitFor(() => expect(puts).toEqual([{ profile_id: 1, dose_ml: 185, compensation_enabled: true }]));
  });

  it('explains DOSE_OUT_OF_RANGE with the API’s range', async () => {
    onPut(() =>
      HttpResponse.json(
        { code: 'DOSE_OUT_OF_RANGE', message: 'dose must be between 28 and 816 mL', detail: { min_ml: 27.2, max_ml: 816 } },
        { status: 422 },
      ),
    );
    renderCard();
    await userEvent.click(screen.getByRole('button', { name: /Light/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('It can dose 27–816 mL.');
  });

  it('warns when the dose is capped as the bottle runs low', () => {
    renderCard(makeDevice({ dosing: makeDosing({ dose_ml: 400, capped_ml_when_low: 204, warning: 'CAPPED_WHEN_LOW' }) }));
    expect(screen.getByText(/can dispense at most about 204 mL per dose/)).toBeInTheDocument();
  });

  it('shows the unknown fill state and sets the level', async () => {
    const bottle = { ...makeDevice().bottle!, initial_fill_ml: null, est_remaining_ml: null, est_doses_left: null, guidance: 'unknown' as const };
    let adjusted: unknown = null;
    server.use(
      http.post(`*/api/v1/devices/${DEVICE_ID}/bottles/current/adjust`, async ({ request }) => {
        adjusted = await request.json();
        return HttpResponse.json(bottle);
      }),
    );
    renderCard(makeDevice({ bottle }));
    expect(screen.getByText('Set the level')).toBeInTheDocument();
    expect(screen.getByText('We don’t know how full the bottle is yet.')).toBeInTheDocument();
    expect(screen.getByRole('meter')).not.toHaveAttribute('aria-valuenow');
    await userEvent.click(screen.getByRole('button', { name: 'Set level' }));
    const sheet = screen.getByRole('dialog', { name: 'Set bottle level' });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Full' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save level' }));
    await waitFor(() => expect(adjusted).toEqual({ fill_ml: 1065 }));
  });

  it('shows the bottle level and doses left from the API', () => {
    renderCard();
    expect(screen.getByText('About 708 mL left · ≈ 4 doses')).toBeInTheDocument();
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '66');
  });

  it('shows the API’s computed valve time in Advanced', async () => {
    renderCard(makeDevice({ dosing: makeDosing({ computed_seconds: 6.4 }) }));
    await userEvent.click(screen.getByRole('button', { name: 'Advanced' }));
    const sheet = screen.getByRole('dialog', { name: 'Advanced dosing' });
    expect(within(sheet).getByTestId('computed-seconds')).toHaveTextContent('6.4');
    expect(within(sheet).getByRole('switch', { name: 'Use a fixed time' })).toHaveAttribute('aria-checked', 'false');
    expect(within(sheet).getByRole('switch', { name: 'Adjust for bottle level' })).toHaveAttribute('aria-checked', 'true');
  });

  it('switches to a fixed time at the current computed seconds', async () => {
    onPut(() => HttpResponse.json(makeDosing()));
    renderCard();
    await userEvent.click(screen.getByRole('button', { name: 'Advanced' }));
    await userEvent.click(screen.getByRole('switch', { name: 'Use a fixed time' }));
    await waitFor(() => expect(puts).toEqual([{ profile_id: 1, fixed_seconds: 6.5, compensation_enabled: true }]));
  });
});

describe('CalibrateSheet', () => {
  async function openAndMeasure(device: DeviceDetail, measured: string) {
    renderCard(device);
    await userEvent.click(screen.getByRole('button', { name: device.dosing.calibrated ? 'Recalibrate' : 'Calibrate' }));
    const sheet = screen.getByRole('dialog', { name: /Calibrate/ });
    await userEvent.click(within(sheet).getByRole('button', { name: 'Next' }));
    await userEvent.click(within(sheet).getByRole('button', { name: 'It dispensed' }));
    expect(within(sheet).getByRole('button', { name: 'Save calibration' })).toBeDisabled();
    await userEvent.type(within(sheet).getByRole('textbox', { name: 'Measured (mL)' }), measured);
    await userEvent.click(within(sheet).getByRole('button', { name: 'Save calibration' }));
    return sheet;
  }

  it('says "Not calibrated yet · Calibrate" for an uncalibrated liquid', () => {
    renderCard(makeDevice({ dosing: makeDosing({ profile: VINEGAR, calibrated: false }) }));
    expect(screen.getByRole('button', { name: 'Vinegar Not calibrated yet' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Calibrate' })).toBeInTheDocument();
  });

  it('explains how to run a dose first on NO_RECENT_DISPENSE', async () => {
    server.use(
      http.post(`${DOSING_URL}/calibration`, () =>
        HttpResponse.json({ code: 'NO_RECENT_DISPENSE', message: 'no confirmed dispense' }, { status: 409 }),
      ),
    );
    const sheet = await openAndMeasure(makeDevice(), '181');
    expect(await within(sheet).findByRole('alert')).toHaveTextContent(/Run one dose into the cup first/);
  });

  it('rejects an implausible amount', async () => {
    server.use(
      http.post(`${DOSING_URL}/calibration`, () =>
        HttpResponse.json({ code: 'CALIBRATION_IMPLAUSIBLE', message: 'implausible' }, { status: 422 }),
      ),
    );
    const sheet = await openAndMeasure(makeDevice(), '9000');
    expect(await within(sheet).findByRole('alert')).toHaveTextContent('too far from what we expected');
  });

  it('shows the measured flow and the API’s new valve time', async () => {
    let body: unknown = null;
    server.use(
      http.post(`${DOSING_URL}/calibration`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(makeDosing({ flow_ml_s: 27.8, computed_seconds: 6.4, flow_scale: 1.02 }));
      }),
    );
    const sheet = await openAndMeasure(makeDevice(), '181');
    expect(await within(sheet).findByRole('status')).toHaveTextContent('Calibrated. Standard measures 27.8 mL/s.');
    expect(within(sheet).getByText('For 177 mL, the valve now opens for 6.4 s.')).toBeInTheDocument();
    expect(body).toEqual({ measured_ml: 181 });
  });
});
