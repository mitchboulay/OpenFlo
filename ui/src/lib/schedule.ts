import type { RuleCreate, RuleKind, ScheduleEntry } from '@/api/types';
import type { Tone } from '@/types/tone';
import { formatClockTime, fromWallTime, toWallTime, zoneLabel } from './time';

/** Weekdays in display order (Sunday first) with their bit in the API's `days_mask` (bit 0 = Monday). */
export const WEEKDAYS = [
  { bit: 6, name: 'Sunday', short: 'Sun' },
  { bit: 0, name: 'Monday', short: 'Mon' },
  { bit: 1, name: 'Tuesday', short: 'Tue' },
  { bit: 2, name: 'Wednesday', short: 'Wed' },
  { bit: 3, name: 'Thursday', short: 'Thu' },
  { bit: 4, name: 'Friday', short: 'Fri' },
  { bit: 5, name: 'Saturday', short: 'Sat' },
] as const;

const SUNDAY = 1 << 6;
const EVERY_DAY = 0b111_1111;
export const INTERVAL_HOURS = { min: 6, max: 720 } as const;

/** The gentle first rule offered when schedules are first turned on (critique-v2, hard question 5). */
export const DEFAULT_RULE: RuleCreate = { kind: 'weekly', local_time: '09:00', days_mask: SUNDAY, dose_count: 1, enabled: true };

/** "09:00" as "9:00 AM": a wall-clock time, so no zone math. */
function clock(hhmm: string): string {
  return formatClockTime(`2000-01-01T${hhmm}:00Z`, 'UTC') ?? hhmm;
}

function daysText(mask: number): string {
  if ((mask & EVERY_DAY) === EVERY_DAY) return 'day';
  const days = WEEKDAYS.filter((day) => mask & (1 << day.bit));
  return days.length === 1 ? days[0]!.name : days.map((day) => day.short).join(', ');
}

/**
 * A rule in plain language in the home's zone: "Every Sunday at 9:00 AM ET · double dose".
 * The API's own `summary` is 24-hour with no zone, so the UI words rules from their fields.
 */
export function ruleLabel(rule: RuleCreate, timeZone: string): string {
  const zone = zoneLabel(timeZone, new Date(), 'shortGeneric');
  const at = (hhmm: string) => `at ${clock(hhmm)}${zone ? ` ${zone}` : ''}`;
  let text: string;
  switch (rule.kind) {
    case 'daily':
      text = `Every day ${at(rule.local_time ?? '')}`;
      break;
    case 'weekly':
      text = `Every ${daysText(rule.days_mask ?? 0)} ${at(rule.local_time ?? '')}`;
      break;
    case 'interval': {
      const hours = rule.interval_hours ?? 0;
      text = hours > 24 && hours % 24 === 0 ? `Every ${hours / 24} days` : `Every ${hours} hours`;
      break;
    }
    case 'once': {
      const wall = rule.at ? toWallTime(rule.at, timeZone) : null;
      const day = rule.at ? new Date(rule.at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone }) : '';
      text = `Once on ${day} ${at(wall?.time ?? '')}`;
      break;
    }
  }
  return rule.dose_count === 2 ? `${text} · double dose` : text;
}

/** The add/edit sheet's form state: wall-clock values in the home zone, as the native inputs hold them. */
export interface RuleDraft {
  kind: RuleKind;
  /** HH:MM. For an interval, the time of the first dose. */
  time: string;
  /** YYYY-MM-DD, for `once` and an interval's first dose. */
  date: string;
  daysMask: number;
  intervalHours: number;
  doubleDose: boolean;
}

/** A draft for an existing rule, or for a new one (Sunday 9:00 AM; today for dated kinds). */
export function draftFromRule(rule: RuleCreate | null, timeZone: string, now: Date = new Date()): RuleDraft {
  const wall = rule?.at ? toWallTime(rule.at, timeZone) : null;
  return {
    kind: rule?.kind ?? 'weekly',
    time: rule?.local_time ?? wall?.time ?? '09:00',
    date: wall?.date ?? toWallTime(now.toISOString(), timeZone).date,
    daysMask: rule?.days_mask ?? SUNDAY,
    intervalHours: rule?.interval_hours ?? 12,
    doubleDose: rule?.dose_count === 2,
  };
}

/** What stops the draft from saving, in plain words; null when it can be sent. */
export function draftProblem(draft: RuleDraft): string | null {
  if (!draft.time) return 'Pick a time.';
  if (draft.kind === 'weekly' && (draft.daysMask & EVERY_DAY) === 0) return 'Pick at least one day.';
  if ((draft.kind === 'once' || draft.kind === 'interval') && !draft.date) return 'Pick a date.';
  const { min, max } = INTERVAL_HOURS;
  if (draft.kind === 'interval' && !(Number.isInteger(draft.intervalHours) && draft.intervalHours >= min && draft.intervalHours <= max)) {
    return `Choose every ${min} to ${max} hours.`;
  }
  return null;
}

/** The request body for a draft: only the fields its kind takes, times converted from the home zone. */
export function draftToRule(draft: RuleDraft, timeZone: string): RuleCreate {
  const base = { kind: draft.kind, dose_count: draft.doubleDose ? 2 : 1, enabled: true } as const;
  const at = () => fromWallTime({ date: draft.date, time: draft.time }, timeZone);
  switch (draft.kind) {
    case 'daily':
      return { ...base, local_time: draft.time };
    case 'weekly':
      return { ...base, local_time: draft.time, days_mask: draft.daysMask };
    case 'interval':
      return { ...base, interval_hours: draft.intervalHours, at: at() };
    case 'once':
      return { ...base, at: at() };
  }
}

export interface EntryStatusLabel {
  label: string;
  tone: Tone;
}

/**
 * The upcoming list's label for an entry the device already holds or has acted on. `pending` is not here:
 * it shows the shared "Waiting for device" badge until the API reports it served.
 */
export function entryStatus(entry: ScheduleEntry): EntryStatusLabel | null {
  switch (entry.status) {
    case 'pending':
      return null;
    case 'served':
      return { label: 'On device', tone: 'neutral' };
    case 'fired':
      return { label: 'Dispensed', tone: 'ok' };
    case 'missed':
      return { label: 'Missed', tone: 'bad' };
    case 'cleared':
      return entry.reason === 'too_soon'
        ? { label: 'Skipped: too close to a check-in', tone: 'warn' }
        : { label: 'Skipped: schedules were paused', tone: 'neutral' };
  }
}
