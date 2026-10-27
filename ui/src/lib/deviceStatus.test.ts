import { describe, expect, it } from 'vitest';
import { hoursFromNow, makeDevice } from '@/test/fixtures';
import { detailState, headline, isOffline, summaryState } from './deviceStatus';

const TZ = 'America/New_York';
const bottle = makeDevice().bottle!;
const flag = {
  id: 1,
  kind: 'ip_conflict' as const,
  detail: { source_ips: ['203.0.113.7'], changes: [], field: null, old: null, new: null },
  raised_at: hoursFromNow(-1),
  acked_at: null,
  acked_by: null,
};

describe('device status', () => {
  it('is offline only once an hour past the expected check-in', () => {
    const now = new Date();
    expect(isOffline(hoursFromNow(-0.5), now)).toBe(false);
    expect(isOffline(hoursFromNow(-2), now)).toBe(true);
    expect(isOffline(null, now)).toBe(false);
  });

  it('picks the headline by priority: offline › bottle low › level unknown › battery low › fine', () => {
    const offline = makeDevice({ next_expected_sync: hoursFromNow(-3), battery_level: 5, bottle: { ...bottle, guidance: 'refill_now' } });
    expect(detailState(offline).condition).toBe('offline');
    const low = makeDevice({ battery_level: 5, bottle: { ...bottle, guidance: 'refill_soon' } });
    expect(detailState(low).condition).toBe('refill_soon');
    const unknown = makeDevice({ battery_level: 5, bottle: { ...bottle, guidance: 'unknown' } });
    expect(detailState(unknown).condition).toBe('level_unknown');
    expect(detailState(makeDevice({ battery_level: 19 })).condition).toBe('battery_low');
    expect(detailState(makeDevice({ battery_level: 20 }))).toEqual({ condition: 'ok', tone: 'ok', label: 'OK' });
  });

  it('puts lifecycle, an open flag and a paused lock ahead of the bottle', () => {
    const lowBottle = { ...bottle, guidance: 'refill_now' as const };
    expect(detailState(makeDevice({ status: 'retired', bottle: lowBottle })).condition).toBe('retired');
    expect(detailState(makeDevice({ retire_requested_at: hoursFromNow(0) })).condition).toBe('retiring');
    expect(detailState(makeDevice({ flags: [flag], bottle: lowBottle })).condition).toBe('flagged');
    expect(detailState(makeDevice({ flags: [{ ...flag, acked_at: hoursFromNow(0) }] })).condition).toBe('ok');
    const paused = makeDevice({ controls: { ...makeDevice().controls, dispensing_enabled: false }, bottle: lowBottle });
    expect(detailState(paused).condition).toBe('paused');
    expect(headline(paused, 'paused', TZ)).toBe('Dispensing is paused.');
  });

  it('leads a fine device’s headline with the next dose the device holds', () => {
    const now = new Date('2026-10-26T16:00:00Z'); // Mon, 12:00 PM EDT
    const scheduled = makeDevice({ next_dose_at: '2026-11-01T14:00:00Z' }); // Sun 9:00 AM EST
    expect(headline(scheduled, 'ok', TZ, now)).toBe('Everything’s fine. Next dose Sun 9:00 AM ET.');
    expect(headline(makeDevice(), 'ok', TZ, now)).toMatch(/^Everything’s fine. Next check-in around /);
  });

  it('treats a missing bottle as an unknown level', () => {
    expect(detailState(makeDevice({ bottle: null })).condition).toBe('level_unknown');
  });

  it('summarises a list card from its summary fields', () => {
    const state = summaryState({
      device_id: 'X',
      name: 'Attic',
      location: null,
      status: 'active',
      battery_level: 64,
      bottle_guidance: 'unknown',
      last_seen: hoursFromNow(-1),
      next_expected_sync: hoursFromNow(1),
      next_dose_at: null,
      pending_count: 0,
      flagged: false,
    });
    expect(state).toEqual({ condition: 'level_unknown', tone: 'warn', label: 'Needs attention' });
  });
});
