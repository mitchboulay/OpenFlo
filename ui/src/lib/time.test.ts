import { describe, expect, it } from 'vitest';
import {
  formatClockTime,
  formatDate,
  formatDateTime,
  formatRelative,
  formatWhen,
  fromWallTime,
  toWallTime,
  zoneLabel,
} from './time';

const TZ = 'America/New_York';
const NOW = new Date('2026-10-26T16:00:00Z'); // Mon Oct 26, 12:00 PM EDT

describe('time formatting', () => {
  it('formats clock times in the home zone, optionally with the zone', () => {
    expect(formatClockTime('2026-10-26T20:42:00Z', TZ)).toBe('4:42 PM');
    expect(formatClockTime('2026-10-26T20:42:00Z', TZ, true)).toBe('4:42 PM EDT');
    expect(formatClockTime(null)).toBeNull();
    expect(formatClockTime('not a date')).toBeNull();
  });

  it('says today, tomorrow, yesterday, a weekday, or a date', () => {
    expect(formatWhen('2026-10-26T20:42:00Z', TZ, NOW)).toBe('4:42 PM');
    expect(formatWhen('2026-10-27T13:00:00Z', TZ, NOW)).toBe('tomorrow 9:00 AM');
    expect(formatWhen('2026-10-25T13:00:00Z', TZ, NOW)).toBe('yesterday 9:00 AM');
    expect(formatWhen('2026-10-29T13:00:00Z', TZ, NOW)).toBe('Thu 9:00 AM');
    expect(formatWhen('2026-11-18T14:00:00Z', TZ, NOW)).toBe('Nov 18, 9:00 AM');
  });

  it('formats history dates and calendar dates', () => {
    expect(formatDateTime('2026-10-25T13:00:00Z', TZ)).toBe('Sun, Oct 25 · 9:00 AM');
    expect(formatDate('2026-10-26T20:36:40Z', TZ)).toBe('Oct 26, 2026');
    expect(zoneLabel(TZ, NOW)).toBe('EDT');
    expect(zoneLabel(TZ, NOW, 'shortGeneric')).toBe('ET');
  });
});

describe('wall times in the home zone', () => {
  it('converts both ways on either side of a DST change', () => {
    expect(fromWallTime({ date: '2026-10-25', time: '09:00' }, TZ)).toBe('2026-10-25T13:00:00.000Z'); // EDT
    expect(fromWallTime({ date: '2026-11-08', time: '09:00' }, TZ)).toBe('2026-11-08T14:00:00.000Z'); // EST
    expect(toWallTime('2026-11-08T14:00:00Z', TZ)).toEqual({ date: '2026-11-08', time: '09:00' });
    expect(toWallTime('2026-10-27T03:30:00Z', TZ)).toEqual({ date: '2026-10-26', time: '23:30' });
    expect(fromWallTime({ date: '2026-07-01', time: '00:15' }, 'Asia/Kolkata')).toBe('2026-06-30T18:45:00.000Z');
  });

  it('formats past instants relative to now', () => {
    expect(formatRelative('2026-10-26T15:59:30Z', NOW)).toBe('just now');
    expect(formatRelative('2026-10-26T15:55:00Z', NOW)).toBe('5 minutes ago');
    expect(formatRelative('2026-10-26T13:00:00Z', NOW)).toBe('3 hours ago');
    expect(formatRelative('2026-10-25T15:00:00Z', NOW)).toBe('yesterday');
    expect(formatRelative('2026-10-23T16:00:00Z', NOW)).toBe('3 days ago');
    expect(formatRelative(null, NOW)).toBeNull();
  });
});
