import { describe, expect, it } from 'vitest';
import type { ScheduleEntry } from '@/api/types';
import { DEFAULT_RULE, draftFromRule, draftProblem, draftToRule, entryStatus, ruleLabel } from './schedule';

const TZ = 'America/New_York';
const NOW = new Date('2026-10-26T16:00:00Z'); // Mon Oct 26, 12:00 PM EDT

describe('ruleLabel', () => {
  it('words each kind in the home zone, with the DST-free zone name', () => {
    expect(ruleLabel(DEFAULT_RULE, TZ)).toBe('Every Sunday at 9:00 AM ET');
    expect(ruleLabel({ ...DEFAULT_RULE, kind: 'daily', local_time: '19:30', dose_count: 2 }, TZ)).toBe('Every day at 7:30 PM ET · double dose');
    expect(ruleLabel({ ...DEFAULT_RULE, days_mask: 0b101 }, TZ)).toBe('Every Mon, Wed at 9:00 AM ET');
    expect(ruleLabel({ ...DEFAULT_RULE, days_mask: 127 }, TZ)).toBe('Every day at 9:00 AM ET');
    expect(ruleLabel({ kind: 'interval', interval_hours: 12, dose_count: 1, enabled: true }, TZ)).toBe('Every 12 hours');
    expect(ruleLabel({ kind: 'interval', interval_hours: 336, dose_count: 1, enabled: true }, TZ)).toBe('Every 14 days');
    expect(ruleLabel({ kind: 'once', at: '2026-11-03T13:00:00Z', dose_count: 1, enabled: true }, TZ)).toBe('Once on Nov 3 at 8:00 AM ET');
  });
});

describe('rule drafts', () => {
  it('starts a new rule on Sunday at 9:00 AM, dated today in the home zone', () => {
    const draft = draftFromRule(null, TZ, new Date('2026-10-27T02:00:00Z')); // still Oct 26 in New York
    expect(draft).toEqual({ kind: 'weekly', time: '09:00', date: '2026-10-26', daysMask: 64, intervalHours: 12, doubleDose: false });
    expect(draftToRule(draft, TZ)).toEqual(DEFAULT_RULE);
  });

  it('sends a once rule as the UTC instant of the home’s wall-clock time, across DST', () => {
    const before = draftToRule({ ...draftFromRule(null, TZ, NOW), kind: 'once', date: '2026-10-31', time: '08:00' }, TZ);
    const after = draftToRule({ ...draftFromRule(null, TZ, NOW), kind: 'once', date: '2026-11-07', time: '08:00' }, TZ);
    expect(before).toEqual({ kind: 'once', at: '2026-10-31T12:00:00.000Z', dose_count: 1, enabled: true });
    expect(after.at).toBe('2026-11-07T13:00:00.000Z');
  });

  it('round-trips an existing rule and names what blocks saving', () => {
    const rule = { kind: 'interval', interval_hours: 48, at: '2026-11-01T14:00:00Z', dose_count: 2, enabled: true } as const;
    const draft = draftFromRule(rule, TZ, NOW);
    expect(draft).toMatchObject({ kind: 'interval', date: '2026-11-01', time: '09:00', intervalHours: 48, doubleDose: true });
    expect(draftToRule(draft, TZ)).toEqual({ kind: 'interval', interval_hours: 48, at: '2026-11-01T14:00:00.000Z', dose_count: 2, enabled: true });
    expect(draftProblem(draft)).toBeNull();
    expect(draftProblem({ ...draft, intervalHours: 5 })).toBe('Choose every 6 to 720 hours.');
    expect(draftProblem({ ...draft, kind: 'weekly', daysMask: 0 })).toBe('Pick at least one day.');
    expect(draftProblem({ ...draft, time: '' })).toBe('Pick a time.');
  });
});

describe('entryStatus', () => {
  const entry = (status: ScheduleEntry['status'], reason: ScheduleEntry['reason'] = null): ScheduleEntry =>
    ({ id: 1, at: '2026-11-01T14:00:00Z', dose_count: 1, status, reason, rule_ids: [1] });

  it('labels every state; pending is left to the Waiting-for-device badge', () => {
    expect(entryStatus(entry('pending'))).toBeNull();
    expect(entryStatus(entry('served'))?.label).toBe('On device');
    expect(entryStatus(entry('fired'))?.label).toBe('Dispensed');
    expect(entryStatus(entry('missed'))?.label).toBe('Missed');
    expect(entryStatus(entry('cleared', 'too_soon'))?.label).toBe('Skipped: too close to a check-in');
    expect(entryStatus(entry('cleared', 'paused'))?.label).toBe('Skipped: schedules were paused');
  });
});
