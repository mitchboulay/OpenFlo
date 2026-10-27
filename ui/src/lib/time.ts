function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Formats an ISO-8601 instant as a local clock time, e.g. "4:42 PM" (or "4:42 PM EDT" with `withZone`).
 * Returns null for a missing or unparseable value so callers can drop the part.
 */
export function formatClockTime(
  iso: string | null | undefined,
  timeZone?: string,
  withZone = false,
): string | null {
  const date = parse(iso);
  if (!date) return null;
  return date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
    timeZoneName: withZone ? 'short' : undefined,
  });
}

/** Calendar day of `date` in `timeZone` as YYYY-MM-DD, for same-day comparisons. */
function dayKey(date: Date, timeZone?: string): string {
  return date.toLocaleDateString('en-CA', { timeZone });
}

const DAY_MS = 86_400_000;

/**
 * A short relative time in the home's zone: "4:42 PM", "tomorrow 4:42 PM", "yesterday 9:00 AM",
 * "Sun 9:00 AM" within a week, else "Oct 18, 9:00 AM".
 */
export function formatWhen(iso: string | null | undefined, timeZone?: string, now: Date = new Date()): string | null {
  const date = parse(iso);
  if (!date) return null;
  const clock = formatClockTime(iso, timeZone);
  const day = dayKey(date, timeZone);
  if (day === dayKey(now, timeZone)) return clock;
  if (day === dayKey(new Date(now.getTime() + DAY_MS), timeZone)) return `tomorrow ${clock}`;
  if (day === dayKey(new Date(now.getTime() - DAY_MS), timeZone)) return `yesterday ${clock}`;
  const withinWeek = Math.abs(date.getTime() - now.getTime()) < 6 * DAY_MS;
  const prefix = date.toLocaleDateString(undefined, withinWeek
    ? { weekday: 'short', timeZone }
    : { month: 'short', day: 'numeric', timeZone });
  return `${prefix}${withinWeek ? '' : ','} ${clock}`;
}

/** A full date and time for history rows, e.g. "Sun, Oct 25 · 9:00 AM". */
export function formatDateTime(iso: string | null | undefined, timeZone?: string): string | null {
  const date = parse(iso);
  if (!date) return null;
  const day = date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', timeZone });
  return `${day} · ${formatClockTime(iso, timeZone)}`;
}

/**
 * The zone's short name right now, e.g. "EDT"; null when the runtime has none.
 * `shortGeneric` gives the DST-free name ("ET") for times that repeat across a DST change, like schedule rules.
 */
export function zoneLabel(
  timeZone: string | undefined,
  now: Date = new Date(),
  style: 'short' | 'shortGeneric' = 'short',
): string | null {
  const parts = new Intl.DateTimeFormat(undefined, { timeZone, timeZoneName: style }).formatToParts(now);
  return parts.find((part) => part.type === 'timeZoneName')?.value ?? null;
}

/** A wall-clock date and time in some zone, as the native inputs give them: "2026-11-03" and "08:00". */
export interface WallTime {
  date: string;
  time: string;
}

/** `iso` as a wall-clock date and time in `timeZone`. */
export function toWallTime(iso: string, timeZone: string): WallTime {
  const date = new Date(iso);
  return {
    date: dayKey(date, timeZone),
    time: date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone }),
  };
}

/** Milliseconds `timeZone` is ahead of UTC at the instant `utcMs` (whole minutes). */
function zoneOffsetMs(utcMs: number, timeZone: string): number {
  const { date, time } = toWallTime(new Date(utcMs).toISOString(), timeZone);
  return Date.parse(`${date}T${time}:00Z`) - Math.floor(utcMs / 60_000) * 60_000;
}

/**
 * The UTC instant (ISO) of a wall-clock time in `timeZone`, e.g. 9:00 AM in New York on either side of a DST
 * change. A time skipped by spring-forward lands an hour later, as clocks do.
 */
export function fromWallTime({ date, time }: WallTime, timeZone: string): string {
  const wall = Date.parse(`${date}T${time}:00Z`);
  const guess = wall - zoneOffsetMs(wall, timeZone);
  return new Date(wall - zoneOffsetMs(guess, timeZone)).toISOString();
}

const RELATIVE_UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ['day', DAY_MS],
  ['hour', 3_600_000],
  ['minute', 60_000],
];

/** A past instant relative to now: "just now", "5 minutes ago", "yesterday", "3 days ago". */
export function formatRelative(iso: string | null | undefined, now: Date = new Date()): string | null {
  const date = parse(iso);
  if (!date) return null;
  const elapsed = now.getTime() - date.getTime();
  const format = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  for (const [unit, ms] of RELATIVE_UNITS) {
    if (elapsed >= ms) return format.format(-Math.floor(elapsed / ms), unit);
  }
  return 'just now';
}

/** A calendar date, e.g. "Oct 26, 2026". */
export function formatDate(iso: string | null | undefined, timeZone?: string): string | null {
  const date = parse(iso);
  if (!date) return null;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', timeZone });
}
